"""Versioned list prices; never an invoice or a cross-vendor quality score."""
SNAPSHOT_DATE = "2026-10-03"
ELEVEN_MODELS = {"eleven_flash_v2_5": 0.04, "eleven_turbo_v2_5": 0.04,
                 "eleven_multilingual_v2": 0.08, "eleven_v3": 0.08}


def model_rate(model: str) -> float:
    if model not in ELEVEN_MODELS and model != "tts-1":
        raise ValueError("Unknown model price. Set price_per_1k_characters explicitly.")
    return ELEVEN_MODELS.get(model, 0.015)


def estimate(storyboard, model_id="eleven_flash_v2_5", rate=None):
    chars = storyboard.characters
    selected_rate = model_rate(model_id) if rate is None else rate
    # Credits are legacy telemetry only; account billing mode must be confirmed separately.
    comparisons = []
    for model, price in ELEVEN_MODELS.items():
        comparisons.append({"provider": "ElevenLabs", "model": model,
                            "estimate_usd": round(chars / 1000 * price, 6),
                            "basis": f"${price:.2f}/1K characters; current API list price"})
    for provider, model, price in [("OpenAI", "tts-1", 0.015), ("Google", "Neural2", 0.016),
                                   ("Google", "Chirp 3 HD", 0.030)]:
        comparisons.append({"provider": provider, "model": model,
                            "estimate_usd": round(chars / 1000 * price, 6),
                            "basis": f"${price * 1000:g}/1M characters; excludes free allowances"})
    comparisons.append({"provider": "OpenAI", "model": "gpt-4o-mini-tts", "estimate_usd": None,
                        "basis": "$0.60/1M input text tokens + $12/1M output audio tokens; "
                                 "cannot infer exact cost from characters"})
    return {"characters": chars, "selected_model": model_id,
            "estimated_usd": round(chars / 1000 * selected_rate, 6),
            "price_per_1k_characters": selected_rate,
            "comparisons": comparisons, "snapshot_date": SNAPSHOT_DATE,
            "note": "List-price projection, not an invoice. Legacy ElevenLabs accounts, subscriptions, "
                    "taxes, normalization, custom voices and regeneration can change actual charges."}
