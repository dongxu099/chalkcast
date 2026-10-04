import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from chalkcast.billing import amount, claim_planner_usage, request_cost, write_json
from chalkcast.pipeline import run
from chalkcast.planner import plan
from chalkcast.schema import RenderOptions, Storyboard
from chalkcast.server import create_app


@pytest.fixture
def board():
    return Storyboard.model_validate_json(Path("examples/quickstart.json").read_text())


def usage(cost=.002):
    return {"usage_id": "fixture", "model": "fixture-model", "provider": "openrouter.ai",
            "prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300,
            "provider_reported_usd": cost}


@pytest.mark.parametrize("value", [None, True, "0.1", -1, float("nan"), float("inf")])
def test_unknown_or_invalid_amount_is_never_zero(value):
    assert amount(value) is None


def test_receipt_sums_reported_planner_with_estimated_elevenlabs(tmp_path):
    path = tmp_path / "usage.json"
    write_json(path, usage())
    receipt = request_cost({"provider": "elevenlabs", "new_characters": 1000,
                            "estimated_usd": .04, "provider_character_cost": 500},
                           claim_planner_usage(path, "first"))
    assert receipt["planner"]["total_tokens"] == 300
    assert receipt["elevenlabs_estimated_usd"] == .04
    assert receipt["total_estimated_usd"] == pytest.approx(.042)
    assert receipt["basis"] == "estimated"
    assert receipt["elevenlabs_provider_reported_usd"] is None
    assert receipt["total_provider_reported_usd"] is None


def test_missing_planner_cost_keeps_full_total_unknown(tmp_path):
    path = tmp_path / "usage.json"
    write_json(path, usage(None))
    receipt = request_cost({"provider": "elevenlabs", "new_characters": 1000, "estimated_usd": .04},
                           claim_planner_usage(path, "first"))
    assert receipt["total_estimated_usd"] is None
    assert receipt["known_subtotal_usd"] == .04
    assert receipt["unknown_components"] == ["planner_usd"]


def test_planning_fee_is_claimed_once_even_with_parallel_readers(tmp_path):
    path = tmp_path / "usage.json"
    write_json(path, usage())
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda i: claim_planner_usage(path, str(i)), range(4)))
    assert sum(c["state"] == "new" for c in claims) == 1
    assert sum(c["provider_reported_usd"] for c in claims) == .002
    assert sum(c["total_tokens"] for c in claims) == 300
    assert all(c["source_usage"]["total_tokens"] == 300 for c in claims)


def test_full_cache_repeat_costs_zero_and_keeps_original_usage(board, tmp_path):
    path = tmp_path / "storyboard.usage.json"
    write_json(path, usage())
    options = RenderOptions(render=False)
    first = run(board, options, tmp_path / "first", tmp_path / "cache", planner_usage_path=path)
    second = run(board, options, tmp_path / "second", tmp_path / "cache", planner_usage_path=path)
    assert first["request_cost"]["total_estimated_usd"] == .002
    assert second["request_cost"]["total_estimated_usd"] == 0
    assert second["request_cost"]["basis"] == "no_new_api_usage"
    assert second["request_cost"]["planner"]["total_tokens"] == 0
    assert second["request_cost"]["planner"]["source_usage"]["total_tokens"] == 300
    assert second["cache_hits"] == len(board.scenes)


def test_partial_failure_preserves_completed_spend_and_flags_uncertain_call(board, tmp_path, monkeypatch):
    path = tmp_path / "usage.json"
    write_json(path, usage())
    audio = tmp_path / "fixture.mp3"
    audio.write_bytes(b"fixture")
    calls = []

    def synthesize(text, *args, **kwargs):
        calls.append(text)
        if len(calls) == 2:
            raise ValueError("Unconfirmed speech response")
        return {"characters": len(text), "seconds": 1, "cache_hit": False,
                "provider_character_cost": 123, "captions": [], "path": str(audio)}

    monkeypatch.setattr("chalkcast.pipeline.synthesize", synthesize)
    with pytest.raises(ValueError, match="Unconfirmed"):
        run(board, RenderOptions(provider="elevenlabs", render=False), tmp_path / "job", tmp_path / "cache",
            planner_usage_path=path)
    report = json.loads((tmp_path / "job" / "report.json").read_text())
    receipt = report["request_cost"]
    assert report["status"] == "failed"
    assert report["new_characters"] == len(board.scenes[0].narration)
    assert receipt["known_subtotal_usd"] == pytest.approx(.002 + report["estimated_usd"])
    assert receipt["total_estimated_usd"] is None
    assert receipt["elevenlabs_estimated_usd"] is None
    assert receipt["narration"]["unconfirmed_charge"] is True


def test_preflight_failure_still_has_planner_receipt(board, tmp_path):
    path = tmp_path / "usage.json"
    write_json(path, usage())
    with pytest.raises(ValueError, match="No narration request"):
        run(board, RenderOptions(provider="elevenlabs", max_cost_usd=0), tmp_path / "job", tmp_path / "cache",
            planner_usage_path=path)
    receipt = json.loads((tmp_path / "job" / "report.json").read_text())["request_cost"]
    assert receipt["total_estimated_usd"] == .002
    assert receipt["elevenlabs_estimated_usd"] == 0
    assert not receipt["narration"]["unconfirmed_charge"]


@pytest.mark.parametrize("valid", [True, False])
def test_paid_planner_usage_survives_schema_validation(board, tmp_path, monkeypatch, valid):
    monkeypatch.setenv("PLANNER_API_KEY", "fixture-key")
    monkeypatch.setenv("PLANNER_BASE_URL", "https://openrouter.ai/api/v1")
    payload = {"model": "fixture-model", "choices": [{"message": {
        "content": board.model_dump_json() if valid else '{"title":"Missing scenes"}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300, "cost": .002}}
    monkeypatch.setattr("chalkcast.planner.httpx.post", lambda *a, **k: httpx.Response(200, json=payload))
    path = tmp_path / "usage.json"
    if valid:
        plan("Bayesian reasoning", usage_path=path)
    else:
        with pytest.raises(ValueError, match="invalid storyboard"):
            plan("Bayesian reasoning", usage_path=path)
    receipt = json.loads(path.read_text())
    assert receipt["provider_reported_usd"] == .002
    assert receipt["total_tokens"] == 300
    assert receipt["status"] == ("completed" if valid else "invalid_storyboard")


def test_unknown_compatible_provider_cost_unit_is_not_assumed_usd(board, tmp_path, monkeypatch):
    monkeypatch.setenv("PLANNER_API_KEY", "fixture-key")
    monkeypatch.setenv("PLANNER_BASE_URL", "https://compatible.example/v1")
    payload = {"choices": [{"message": {"content": board.model_dump_json()}}],
               "usage": {"total_tokens": 300, "cost": 12345}}
    monkeypatch.setattr("chalkcast.planner.httpx.post", lambda *a, **k: httpx.Response(200, json=payload))
    path = tmp_path / "usage.json"
    plan("Bayesian reasoning", usage_path=path)
    assert json.loads(path.read_text())["provider_reported_usd"] is None


def wait_for_job(client, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(.01)
    pytest.fail("Local job did not finish")


def test_studio_binds_usage_to_draft_not_shared_latest(board, tmp_path, monkeypatch):
    def fake_plan(topic, audience, language, usage_path):
        write_json(usage_path, usage(.001 if topic == "first topic" else .009))
        return board

    monkeypatch.setattr("chalkcast.server.plan", fake_plan)
    client = TestClient(create_app(tmp_path))
    first = client.post("/api/plans", json={"topic": "first topic"}).json()
    client.post("/api/plans", json={"topic": "second topic"})
    assert client.get("/api/planner-usage").json()["provider_reported_usd"] == .009
    body = {"storyboard": first["storyboard"], "planning_id": first["planning_id"], "render": False}
    job_id = client.post("/api/jobs", json=body).json()["id"]
    job = wait_for_job(client, job_id)
    assert job["status"] == "completed"
    assert job["report"]["request_cost"]["total_estimated_usd"] == .001
    # A restarted Studio reads the durable receipt and does not allocate the draft twice.
    restarted = TestClient(create_app(tmp_path))
    second_id = restarted.post("/api/jobs", json=body).json()["id"]
    repeated = wait_for_job(restarted, second_id)
    assert repeated["report"]["request_cost"]["total_estimated_usd"] == 0
    downloaded = restarted.get(repeated["artifacts"]["report"]).json()
    assert downloaded["request_cost"] == repeated["report"]["request_cost"]
    assert restarted.post("/api/jobs", json={**body, "planning_id": "a" * 32}).status_code == 404
    assert restarted.post("/api/jobs", json={**body, "planning_id": "../usage"}).status_code == 422


def test_studio_failure_exposes_downloadable_partial_receipt(board, tmp_path):
    client = TestClient(create_app(tmp_path))
    body = {"storyboard": board.model_dump(), "provider": "elevenlabs", "max_cost_usd": 0}
    job_id = client.post("/api/jobs", json=body).json()["id"]
    job = wait_for_job(client, job_id)
    assert job["status"] == "failed"
    assert job["report"]["request_cost"]["total_estimated_usd"] == 0
    assert client.get(job["artifacts"]["report"]).status_code == 200
