"""Character-aligned captions, with a visibly documented fallback."""

def caption_spans(text, width=62):
    spans, start = [], 0
    while start < len(text):
        end = min(len(text), start + width)
        if end < len(text):
            candidates = [i + 1 for i in range(start + width // 2, end) if text[i] in " \n，。！？"]
            if candidates:
                end = candidates[-1]
        spans.append((start, end))
        start = end
    return spans


def preserves_han_text(text, spoken):
    """A phonetic normalization must not replace Han characters in readable subtitles."""
    def han(value):
        return "".join(c for c in value if "\u3400" <= c <= "\u9fff"
                       or "\uf900" <= c <= "\ufaff" or "\U00020000" <= c <= "\U0002fa1f")
    original = han(text)
    return not original or original == han(spoken)


def captions(text: str, seconds: float, alignment: dict | None, normalized_alignment: dict | None = None):
    for candidate in (normalized_alignment, alignment):
        if not isinstance(candidate, dict):
            continue
        alignment = candidate
        chars = alignment.get("characters", [])
        starts = alignment.get("character_start_times_seconds", [])
        ends = alignment.get("character_end_times_seconds", [])
        if (isinstance(chars, list) and isinstance(starts, list) and isinstance(ends, list)
                and len(chars) == len(starts) == len(ends) and chars
                and all(isinstance(c, str) for c in chars)
                and all(isinstance(t, (int, float)) for t in starts + ends)):
            # English number expansions are useful, but Chinese normalization can be pinyin.
            spoken = "".join(chars)
            if not preserves_han_text(text, spoken):
                continue
            chunks = caption_spans(spoken)
            result = []
            for a, b in chunks:
                start, end = float(starts[a]), float(ends[b - 1])
                if 0 <= start < seconds and start <= end <= seconds + 0.5:
                    result.append({"start": start, "end": min(seconds, end),
                                   "text": spoken[a:b].strip()})
            if result and len(result) == len(chunks):
                return result, "provider_character_alignment"
    words = [text[a:b] for a, b in caption_spans(text, 60)]
    total = sum(len(w) for w in words) or 1
    result, cursor = [], 0.0
    for chunk in words:
        end = cursor + seconds * len(chunk) / total
        result.append({"start": cursor, "end": end, "text": chunk.strip()})
        cursor = end
    return result, "estimated_proportional_timing"


def stamp(seconds):
    millis = round(seconds * 1000)
    hours, rem = divmod(millis, 3600000)
    minutes, rem = divmod(rem, 60000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def srt(cues):
    return "\n\n".join(f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}"
                       for i, c in enumerate(cues, 1)) + "\n"
