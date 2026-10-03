"""Narration adapters with explicit retries, immutable cache entries and sanitized errors."""
import base64
import hashlib
import json
import os
import tempfile
import time
import wave
from pathlib import Path

import httpx
from mutagen.mp3 import MP3

from .captions import captions


def read_cache_record(path):
    try:
        record = json.loads(path.read_text())
        if not isinstance(record, dict) or not isinstance(record.get("filename"), str):
            raise ValueError("Invalid cache contract")
        return record
    except (ValueError, OSError) as exc:
        raise ValueError("Audio cache checkpoint is unreadable. No request was resent. Inspect the "
                         "cache and account usage before explicitly removing the checkpoint.") from exc


def write_cache_record(path, record):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, suffix=".tmp", delete=False) as temp:
        temp.write(json.dumps(record, ensure_ascii=False, indent=2))
        name = temp.name
    os.replace(name, path)


def cache_key(text, options, previous="", following=""):
    contract = {"version": 1, "provider": options.provider, "model": options.model_id,
                "voice": options.voice_id, "text": text, "previous": previous, "next": following,
                "output_format": "mp3_44100_128", "settings": {"stability": 0.5, "similarity_boost": 0.75}}
    return hashlib.sha256(json.dumps(contract, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def silent_duration(text):
    cjk = sum("\u3400" <= c <= "\u9fff" for c in text)
    return max(3, min(35, (len(text.split()) / 2.5) if cjk == 0 else len(text) / 4))


def synthesize(text, options, cache_dir: Path, previous="", following="", client=None):
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = cache_key(text, options, previous, following)
    metadata_path = cache_dir / f"{key}.json"
    if metadata_path.exists():
        cached = read_cache_record(metadata_path)
        if cached.get("state") in {"rejected", "uncertain"}:
            raise ValueError("A prior narration response is checkpointed and may have been billed. "
                             "No request was resent. Inspect account usage and the cache checkpoint "
                             "before explicitly removing it to retry.")
        path = cache_dir / cached["filename"]
        if path.is_file() and path.stat().st_size > 0:
            return {**cached, "path": str(path), "cache_hit": True, "wall_seconds": 0,
                    "provider_character_cost": None}
    began = time.perf_counter()
    alignment, observed, raw_cost, request_id, trace_id = None, None, None, None, None
    def checkpoint(reason, state="rejected"):
        write_cache_record(metadata_path, {"state": state, "reason": reason,
                                          "filename": f"{key}.mp3", "request_id": request_id,
                                          "provider_character_cost": observed})
    if options.provider == "silent":
        seconds = silent_duration(text)
        filename = f"{key}.wav"
        path = cache_dir / filename
        with wave.open(str(path), "wb") as audio:
            audio.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            audio.writeframes(b"\0\0" * round(seconds * 22050))
    else:
        service_key = "ELEVENLABS_API_KEY" if options.provider == "elevenlabs" else "OPENAI_API_KEY"
        secret = os.environ.get(service_key)
        if not secret or secret.startswith("replace-"):
            raise ValueError(f"Inject {service_key} in the server process before generating narration.")
        own_client = client is None
        client = client or httpx.Client(timeout=120)
        try:
            if options.provider == "elevenlabs":
                if options.model_id not in {"eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2"}:
                    raise ValueError("Live timestamp narration supports Flash/Turbo v2.5 and Multilingual v2.")
                response = client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{options.voice_id}/with-timestamps",
                    params={"output_format": "mp3_44100_128"}, headers={"xi-api-key": secret},
                    json={"text": text, "model_id": options.model_id,
                          "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                          "previous_text": previous, "next_text": following})
            else:
                if options.model_id != "tts-1":
                    raise ValueError("OpenAI live comparison currently supports tts-1 only.")
                response = client.post("https://api.openai.com/v1/audio/speech",
                                       headers={"Authorization": f"Bearer {secret}"},
                                       json={"model": "tts-1", "voice": options.voice_id,
                                             "input": text, "response_format": "mp3"})
        except httpx.HTTPError as exc:
            checkpoint("Network failure; billing outcome unknown", "uncertain")
            raise ValueError("Narration network failure. No automatic retry: the provider may have billed "
                             "the request. Review your account before retrying.") from exc
        finally:
            if own_client:
                client.close()
        if not response.is_success:
            hint = {401: "Check the API key.", 403: "Check permissions and voice access.",
                    402: "Check the billing plan.", 429: "Check quota or concurrency; retry later."}
            raise ValueError(f"Narration returned HTTP {response.status_code}. "
                             + hint.get(response.status_code, "Check model and voice compatibility."))
        filename = f"{key}.mp3"
        path = cache_dir / filename
        request_id = response.headers.get("request-id") or response.headers.get("x-request-id")
        raw_cost = response.headers.get("character-cost")
        try:
            observed = float(raw_cost) if raw_cost is not None else None
        except ValueError:
            observed = None
        checkpoint("Successful response received; audio processing is incomplete")
        if options.provider == "elevenlabs":
            try:
                payload = response.json()
                audio_bytes = base64.b64decode(payload["audio_base64"], validate=True)
                alignment = payload.get("normalized_alignment") or payload.get("alignment")
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError("Provider returned invalid audio JSON; the request may have been billed.") from exc
            trace_id = response.headers.get("x-trace-id")
        else:
            audio_bytes = response.content
            request_id = response.headers.get("x-request-id")
        path.write_bytes(audio_bytes)
        try:
            seconds = MP3(path).info.length
        except Exception as exc:
            path.unlink(missing_ok=True)
            raise ValueError("Provider returned unreadable MP3; the request may have been billed.") from exc
        if not 0 < seconds <= 120:
            checkpoint("Scene duration exceeds the supported range; successful audio is preserved")
            raise ValueError("A scene audio track must be between 0 and 120 seconds. "
                             "The successful response is cached and may have been billed.")
    cues, timing_source = captions(text, seconds, alignment)
    record = {"state": "ready", "filename": filename, "seconds": seconds, "characters": len(text),
              "provider_character_cost": observed, "provider_character_cost_raw": raw_cost,
              "request_id": request_id, "trace_id": trace_id, "captions": cues,
              "timing_source": timing_source, "wall_seconds": round(time.perf_counter() - began, 3)}
    write_cache_record(metadata_path, record)
    return {**record, "path": str(path), "cache_hit": False}
