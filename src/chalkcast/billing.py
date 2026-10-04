"""Per-request API receipts. Unknown charges never become zero-dollar invoices."""
import fcntl
import json
import math
import uuid
from pathlib import Path


def amount(value):
    """Accept only finite, nonnegative JSON numbers from a provider."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def claim_planner_usage(path: Path | None, request_id: str):
    """Allocate a paid draft once, including across CLI runs and server restarts."""
    if path is None:
        return {"state": "not_used", "prompt_tokens": 0, "completion_tokens": 0,
                "total_tokens": 0, "provider_reported_usd": 0, "source_usage": None}
    # Lock a separate file: the receipt itself is replaced atomically.
    with path.with_suffix(path.suffix + ".lock").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        usage = json.loads(path.read_text())
        owner = usage.get("charged_to_request")
        reused = owner is not None and owner != request_id
        if owner is None:
            usage["charged_to_request"] = request_id
            write_json(path, usage)
        fields = {key: amount(usage.get(key)) for key in
                  ("prompt_tokens", "completion_tokens", "total_tokens", "provider_reported_usd")}
        source = {**fields, "model": usage.get("model"), "provider": usage.get("provider"),
                  "usage_id": usage.get("usage_id"), "charged_to_request": usage["charged_to_request"]}
        return {"state": "reused" if reused else "new", **{key: 0 if reused else value
                                                           for key, value in fields.items()},
                "source_usage": source}


def request_cost(report, planner=None, unconfirmed_narration=False):
    """Combine reported planning USD with projected *new* narration, never character-cost."""
    planner = planner or claim_planner_usage(None, "")
    planning_usd = amount(planner.get("provider_reported_usd"))
    narration_usd = amount(report.get("estimated_usd"))
    new_characters = report.get("new_characters", 0)
    provider = report["provider"]
    no_speech_charge = (provider == "silent" or new_characters == 0) and not unconfirmed_narration
    narration_reported = 0 if no_speech_charge else None
    unknown = []
    if planning_usd is None:
        unknown.append("planner_usd")
    if narration_usd is None or unconfirmed_narration:
        unknown.append("narration_usd")
    subtotal = round((planning_usd or 0) + (narration_usd or 0), 10)
    reported_total = (round(planning_usd + narration_reported, 10)
                      if planning_usd is not None and narration_reported is not None else None)
    basis = ("partial" if unknown else "no_new_api_usage" if no_speech_charge and planner["state"] != "new"
             else "provider_reported" if no_speech_charge else "estimated")
    return {"currency": "USD", "planner": planner,
            "narration": {"provider": provider, "new_characters": new_characters,
                          "estimated_usd": narration_usd, "provider_reported_usd": narration_reported,
                          "unconfirmed_charge": unconfirmed_narration},
            "elevenlabs_estimated_usd": (None if unconfirmed_narration else narration_usd)
            if provider == "elevenlabs" else 0,
            "elevenlabs_provider_reported_usd": narration_reported if provider == "elevenlabs" else 0,
            "local_render_api_usd": 0,
            "total_estimated_usd": None if unknown else subtotal,
            "known_subtotal_usd": subtotal, "total_provider_reported_usd": reported_total,
            "unknown_components": unknown,
            "basis": basis,
            "scope": "Incremental API usage for this request. Draft fees are allocated to the first "
                     "render only; cached narration and reused drafts add no API call. Local compute, "
                     "external storyboard authoring, subscriptions, credit-purchase fees, taxes and "
                     "discounts are excluded. "
                     "ElevenLabs USD is a list-rate estimate, not an account cash charge."}
