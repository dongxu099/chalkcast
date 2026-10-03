import base64
import json
import subprocess
from pathlib import Path

import httpx
import imageio_ffmpeg
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from chalkcast.captions import captions, srt
from chalkcast.costs import estimate
from chalkcast.narration import cache_key, synthesize
from chalkcast.pipeline import run
from chalkcast.schema import RenderOptions, Storyboard
from chalkcast.server import create_app


@pytest.fixture
def board():
    return Storyboard.model_validate_json(Path("examples/quickstart.json").read_text())


def test_costs_are_character_based_not_byte_based(board):
    board.scenes[0].narration = "你好" * 100
    result = estimate(board)
    assert result["characters"] == 200 + len(board.scenes[1].narration)
    assert result["estimated_usd"] == round(result["characters"] * 0.04 / 1000, 6)
    assert any(c["model"] == "tts-1" for c in result["comparisons"])
    with pytest.raises(ValueError, match="Unknown"):
        estimate(board, "unpriced-model")


@pytest.mark.parametrize("change", [
    {"values": [float("nan"), 2]}, {"values": [1]}, {"labels": ["x" * 40, "y"]},
    {"kind": "python", "formula": "print('unsafe')"}, {"code": "anything"},
])
def test_schema_rejects_unsafe_or_unrenderable_visuals(board, change):
    data = board.model_dump()
    data["scenes"][1]["visual"].update(change)
    with pytest.raises(ValidationError):
        Storyboard.model_validate(data)


def test_captions_do_not_drop_long_words_or_chinese():
    for text in ["a" * 200, "中文测试" * 70, "Two words. " * 30]:
        cues, source = captions(text, 20, None)
        assert "".join(c["text"] for c in cues).replace(" ", "") == text.replace(" ", "")
        assert source == "estimated_proportional_timing"
        assert cues[-1]["end"] == pytest.approx(20)
        assert "00:00:00,000 -->" in srt(cues)


def test_normalized_alignment_and_invalid_fallback():
    text = "The value is 12."
    spoken = "The value is twelve."
    alignment = {"characters": list(spoken),
                 "character_start_times_seconds": [i * .1 for i in range(len(spoken))],
                 "character_end_times_seconds": [(i + 1) * .1 for i in range(len(spoken))]}
    cues, source = captions(text, 3, alignment)
    assert "twelve" in cues[0]["text"]
    assert source == "provider_character_alignment"
    alignment["character_end_times_seconds"] = []
    assert captions(text, 3, alignment)[1] == "estimated_proportional_timing"


def test_alignment_cannot_produce_reverse_cues():
    alignment = {"characters": ["x"], "character_start_times_seconds": [1.2],
                 "character_end_times_seconds": [1.3]}
    cues, source = captions("x", 1, alignment)
    assert source == "estimated_proportional_timing"
    assert all(0 <= c["start"] <= c["end"] <= 1 for c in cues)


@pytest.mark.parametrize("alignment", ["bad", {"characters": ["a"],
    "character_start_times_seconds": [None], "character_end_times_seconds": ["oops"]}])
def test_malformed_alignment_falls_back(alignment):
    assert captions("hello", 1, alignment)[1] == "estimated_proportional_timing"


@pytest.mark.parametrize("field", ["title", "labels", "caption", "formula"])
def test_multiline_visuals_rejected_before_paid_requests(board, field):
    data = board.model_dump()
    scene = data["scenes"][0]
    if field == "title":
        scene[field] = "First\nSecond"
    elif field == "labels":
        scene["visual"][field] = ["First\nSecond", "other", "third"]
    else:
        scene["visual"][field] = "First\nSecond"
    with pytest.raises(ValidationError, match="single-line"):
        Storyboard.model_validate(data)


def test_multiline_narration_can_render_captions(board):
    from chalkcast.render import frame
    assert frame(board.scenes[0], .5, "First line\nSecond line").size == (1280, 720)


def test_budget_stops_before_any_api_call(board, tmp_path, monkeypatch):
    monkeypatch.setattr("chalkcast.pipeline.synthesize", lambda *a, **k: pytest.fail("API called"))
    with pytest.raises(ValueError, match="No narration request"):
        run(board, RenderOptions(provider="elevenlabs", max_cost_usd=0), tmp_path / "job", tmp_path / "cache")
    with pytest.raises(ValueError, match="max_characters"):
        run(board, RenderOptions(max_characters=1), tmp_path / "job", tmp_path / "cache")


def test_output_folder_cannot_mix_runs(board, tmp_path):
    destination = tmp_path / "job"
    destination.mkdir()
    (destination / "video.mp4").write_bytes(b"previous run")
    with pytest.raises(ValueError, match="fresh run"):
        run(board, RenderOptions(render=False), destination, tmp_path / "cache")
    assert (destination / "video.mp4").read_bytes() == b"previous run"


def test_cache_covers_model_voice_and_context():
    options = RenderOptions()
    baseline = cache_key("hello", options)
    assert baseline != cache_key("hello", options, previous="previous")
    assert baseline != cache_key("hello", options, following="next")
    assert baseline != cache_key("hello", options.model_copy(update={"voice_id": "other"}))
    assert baseline != cache_key("hello", options.model_copy(update={"model_id": "other"}))


def test_silent_pipeline_reuses_audio_and_charges_zero(board, tmp_path):
    opts = RenderOptions(render=False)
    first = run(board, opts, tmp_path / "first", tmp_path / "cache")
    second = run(board, opts, tmp_path / "second", tmp_path / "cache")
    assert first["estimated_usd"] == second["estimated_usd"] == 0
    assert second["cache_hits"] == len(board.scenes)
    assert first["provider_character_cost"] is None
    assert (tmp_path / "second" / "scene_01.wav").is_file()
    assert json.loads((tmp_path / "second" / "report.json").read_text())["provider"] == "silent"


def test_report_counts_within_job_cache_hits(board, tmp_path, monkeypatch):
    scene = board.scenes[0].model_copy(update={"narration": "Hello"})
    board.scenes = [scene] * 4
    audio_path = tmp_path / "fake.mp3"
    audio_path.write_bytes(b"fixture")
    seen = set()
    def fake_synthesize(text, options, cache_dir, previous, following, **kwargs):
        key = cache_key(text, options, previous, following)
        hit = key in seen
        seen.add(key)
        return {"characters": len(text), "seconds": 1, "cache_hit": hit,
                "provider_character_cost": None, "captions": [], "path": str(audio_path)}
    monkeypatch.setattr("chalkcast.pipeline.synthesize", fake_synthesize)
    report = run(board, RenderOptions(provider="elevenlabs", render=False),
                 tmp_path / "job", tmp_path / "cache")
    assert report["cache_hits"] == 1
    assert report["new_characters"] == 15
    assert report["estimated_usd"] == pytest.approx(.0006)


def test_provider_error_is_sanitized_and_not_retried(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-secret")
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"detail": "sensitive test-secret"})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="HTTP 429") as err:
        synthesize("hello", RenderOptions(provider="elevenlabs"), tmp_path, client=client)
    assert len(calls) == 1
    assert "test-secret" not in str(err.value)


def test_successful_but_unusable_response_is_checkpointed(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-secret")
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers={"request-id": "req_bad"}, json={"audio_base64": "invalid"})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    opts = RenderOptions(provider="elevenlabs")
    with pytest.raises(ValueError, match="invalid audio"):
        synthesize("hello", opts, tmp_path, client=client)
    with pytest.raises(ValueError, match="No request was resent"):
        synthesize("hello", opts, tmp_path, client=client)
    assert len(calls) == 1
    record = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert record["request_id"] == "req_bad"
    assert record["state"] == "rejected"


def test_network_failure_blocks_implicit_resend(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-secret")
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout", request=request)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    opts = RenderOptions(provider="elevenlabs")
    with pytest.raises(ValueError, match="network failure"):
        synthesize("hello", opts, tmp_path, client=client)
    with pytest.raises(ValueError, match="No request was resent"):
        synthesize("hello", opts, tmp_path, client=client)
    assert len(calls) == 1


def test_corrupt_checkpoint_stops_before_api(tmp_path, monkeypatch):
    opts = RenderOptions(provider="elevenlabs")
    key = cache_key("hello", opts)
    (tmp_path / f"{key}.json").write_text('{"half":')
    with pytest.raises(ValueError, match="unreadable. No request was resent"):
        synthesize("hello", opts, tmp_path)


def test_elevenlabs_contract_and_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-secret")
    mp3 = tmp_path / "fixture.mp3"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=44100:cl=mono", "-t", "1", str(mp3)], check=True)
    calls = []
    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert request.headers["xi-api-key"] == "test-secret"
        assert payload["previous_text"] == "before"
        assert request.url.path.endswith("/with-timestamps")
        return httpx.Response(200, headers={"character-cost": "2.5", "request-id": "req_test"},
                              json={"audio_base64": base64.b64encode(mp3.read_bytes()).decode(),
                                    "alignment": {"characters": list("hello"),
                                                  "character_start_times_seconds": [0, .1, .2, .3, .4],
                                                  "character_end_times_seconds": [.1, .2, .3, .4, .5]}})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    options = RenderOptions(provider="elevenlabs")
    first = synthesize("hello", options, tmp_path / "cache", "before", client=client)
    second = synthesize("hello", options, tmp_path / "cache", "before", client=client)
    assert first["provider_character_cost"] == 2.5
    assert first["timing_source"] == "provider_character_alignment"
    assert second["cache_hit"]
    assert second["provider_character_cost"] is None
    assert len(calls) == 1


def test_studio_routes_and_origin_protection(tmp_path):
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/config").status_code == 200
    examples = client.get("/api/examples").json()
    board = client.get("/api/examples/" + examples[0]["name"]).json()
    assert client.post("/api/estimate", json={"storyboard": board}).status_code == 200
    assert client.get("/api/examples/invalid.name").status_code == 404
    assert client.get("/artifacts/" + "a" * 32 + "/encoder.log").status_code == 404
    assert client.post("/api/plan", headers={"Origin": "https://example.com"},
                       json={"topic": "test"}).status_code == 403
    assert client.get("/api/config", headers={"Host": "attacker.example.com"}).status_code == 400
