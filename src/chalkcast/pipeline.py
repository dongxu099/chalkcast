import json
import math
import shutil
import time
import uuid
from pathlib import Path

from .billing import claim_planner_usage, request_cost, write_json
from .captions import srt
from .costs import estimate
from .narration import cache_key, read_cache_record, synthesize
from .render import FPS, render_video


def run(storyboard, options, destination: Path, cache_dir: Path, notify=lambda x: None, client=None,
        planner_usage_path: Path | None = None):
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Output folder is not empty. Choose a fresh run folder under the same parent "
                         "to reuse audio cache without mixing old and new artifacts.")
    destination.mkdir(parents=True, exist_ok=True)
    request_id = uuid.uuid4().hex
    planning = claim_planner_usage(planner_usage_path, request_id)
    began = time.perf_counter()
    segments, duration, cursor = [], 0.0, 0.0
    narration_in_flight = False
    report = {"provider": options.provider, "model_id": options.model_id, "voice_id": options.voice_id,
              "request_id": request_id, "planning_id": getattr(options, "planning_id", None),
              "rendered_video": options.render,
              "status": "running", "total_characters": storyboard.characters,
              "new_characters": 0,
              "estimated_usd": 0, "provider_character_cost": None, "cache_hits": 0, "segments": [],
              "limitations": ["Dollar amounts are API usage values, not account cash invoices.",
                              "Full-response latency is not time to first audio byte.",
                              "Silent/OpenAI captions use estimated proportional timing.",
                              "Voice quality needs listening; no automatic quality score is claimed."]}

    def save_receipt():
        costs = [s["provider_character_cost"] for s in segments if not s["cache_hit"]]
        generated_chars = sum(s["characters"] for s in segments if not s["cache_hit"])
        report.update(new_characters=generated_chars if options.provider != "silent" else 0,
                      estimated_usd=round(generated_chars / 1000 * report.get("price_per_1k_characters", 0), 6)
                      if options.provider != "silent" else 0,
                      provider_character_cost=sum(costs) if costs and all(c is not None for c in costs) else None,
                      cache_hits=sum(s["cache_hit"] for s in segments),
                      segments=[{k: v for k, v in s.items() if k != "path"} for s in segments],
                      audio_seconds=round(duration, 3), total_wall_seconds=round(time.perf_counter() - began, 3))
        report["request_cost"] = request_cost(report, planning, narration_in_flight)
        write_json(destination / "report.json", report)

    try:
        save_receipt()
        texts = [s.narration for s in storyboard.scenes]
        if storyboard.characters > options.max_characters:
            raise ValueError("Narration exceeds max_characters. Shorten it or raise the explicit limit.")
        projection = estimate(storyboard, options.model_id, options.price_per_1k_characters)
        report.update(snapshot_date=projection["snapshot_date"], billing_note=projection["note"],
                      price_per_1k_characters=projection["price_per_1k_characters"],
                      comparisons=projection["comparisons"])
        pending_chars, pending_keys = 0, set()
        for i, text in enumerate(texts):
            key = cache_key(text, options, texts[i - 1] if i else "", texts[i + 1] if i + 1 < len(texts) else "")
            record_path = cache_dir / f"{key}.json"
            hit = False
            if record_path.exists():
                record = read_cache_record(record_path)
                audio_path = cache_dir / record["filename"]
                hit = audio_path.is_file() and audio_path.stat().st_size > 0
            if not hit and key not in pending_keys:
                pending_chars += len(text)
                pending_keys.add(key)
        expected_charge = pending_chars / 1000 * projection["price_per_1k_characters"]
        if options.provider != "silent" and expected_charge > options.max_cost_usd + 1e-9:
            raise ValueError(f"Estimated new narration ${expected_charge:.4f} exceeds max_cost_usd. "
                             "No narration request was sent.")
        (destination / "storyboard.json").write_text(storyboard.model_dump_json(indent=2))
        for i, text in enumerate(texts):
            notify(f"Narrating scene {i + 1}/{len(texts)}")
            narration_in_flight = options.provider != "silent"
            segment = synthesize(text, options, cache_dir, texts[i - 1] if i else "",
                                 texts[i + 1] if i + 1 < len(texts) else "", client=client)
            narration_in_flight = False
            duration += segment["seconds"]
            segments.append(segment)
            # Account for the successful request before a copy/encoder can fail.
            save_receipt()
            audio_name = f"scene_{i + 1:02}" + Path(segment["path"]).suffix
            shutil.copyfile(segment["path"], destination / audio_name)
            segment["audio_file"] = audio_name
            (destination / "progress.json").write_text(json.dumps(
                {"completed_scenes": i + 1, "segments": [{k: v for k, v in s.items() if k != "path"}
                                                         for s in segments]}, ensure_ascii=False, indent=2))
            if duration > 600:
                raise ValueError("Total audio exceeded 10 minutes. Completed narration is cached.")
        report["narration_wall_seconds"] = round(time.perf_counter() - began, 3)
        if options.render:
            notify("Rendering animation")
            render_video(storyboard, segments, destination, notify)
        cues = []
        for segment in segments:
            for cue in segment["captions"]:
                cues.append({**cue, "start": cue["start"] + cursor, "end": cue["end"] + cursor})
            cursor += math.ceil(segment["seconds"] * FPS) / FPS if options.render else segment["seconds"]
        (destination / "subtitles.srt").write_text(srt(cues), encoding="utf-8")
        report.update(status="completed", video_seconds=round(cursor, 3))
        save_receipt()
        notify("Completed")
        return report
    except Exception:
        report["status"] = "failed"
        save_receipt()
        raise
