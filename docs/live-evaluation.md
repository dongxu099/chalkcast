# First live ElevenLabs experiment

Measured locally on 2026-10-03. The requests used stock voice `JBFqnCBsd6RMkjVDRZzb`, stability 0.5, similarity boost 0.75 and MP3 44.1 kHz/128 kbps. Each benchmark request used the same 203-character `voice_probe.json` script. Separate trial caches ensured three independent generations per model. Full-response time includes HTTP, audio decoding and caption processing; it is not streaming time to first audio.

| Measurement | Flash v2.5 | Multilingual v2 |
| --- | --- | --- |
| Independent samples | 3 | 3 |
| Full-response seconds | 1.311, 0.928, 1.080 | 3.148, 2.158, 3.109 |
| Median seconds | 1.080 | 3.109 |
| Audio duration range | 15.177–16.431 s | 14.759–15.229 s |
| Raw `character-cost` per request | 102 | 203 |
| List-price projection per request | $0.00812 | $0.01624 |

Flash returned faster complete responses in this small sequential sample. Duration varied across unchanged requests. Neither observation establishes a general latency guarantee or a voice-quality ranking. Audio is available locally for blind listening; no subjective pronunciation or prosody score is claimed.

## English and Chinese video pipeline

- English quickstart: 291 characters, 17.136 seconds of speech, 17.167-second video, 1.346 seconds of narration processing and 7.107 seconds for the whole render. Both scenes used provider alignment.
- Corrected Chinese cache explainer: 99 characters, 23.798 seconds of speech, 23.875-second video, 1.484 seconds of narration processing and 10.119 seconds for the whole render. Both scene captions retain the complete Chinese input and use provider alignment.
- Both containers are 1280×720 H.264 at 24 fps with AAC audio. Representative frames were visually inspected; caption bounds and ordering passed.
- Repeating the unchanged English input produced two cache hits and zero new characters. A client that fails on any HTTP request confirmed that no synthesis request occurred.

## A real integration failure: normalized Chinese text became pinyin

The first Chinese output displayed pinyin. The app preferred `normalized_alignment` and used its characters as readable subtitles. A ten-character live probe, `我们把讲解拆成场景。`, returned exactly those Han characters in `alignment`, but pinyin in `normalized_alignment`.

The fix rejects a candidate that changes the input's Han-character sequence, tries the original alignment, and falls back to source-text captions with estimated timing when neither candidate is reliable. English spoken-number expansion continues to use normalized alignment. The [official endpoint](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps) distinguishes original and normalized text; the live probe exposed why that distinction matters.

New cache records retain both alignment forms. An older Chinese cache without original alignment was repaired without a new API request, using the original text with estimated timing. A separate fresh Chinese run verified the corrected provider-aligned path. The offline suite includes a sanitized [real alignment fixture](../tests/fixtures/chinese_alignment.json), malformed-normalization fallback and no-request legacy-cache repair.

## Cost and permission boundaries

The full experiment submitted 1,717 new characters across 13 TTS requests, including the initial flawed Chinese run, the ten-character probe and the corrected Chinese verification. Total list-price projection: **$0.09304**. Summed raw `character-cost`: **1,165**. These are separate quantities; `character-cost` is not treated as USD or independently verified account credits. See [cost methodology](costs.md).

The key allowed TTS but account and model-list GETs returned HTTP 401 with `missing_permissions`. Thus, successful key loading and a 401 from an unrelated endpoint cannot determine TTS validity. A TTS-only key can support the tool; optional account-read permission would enable before/after quota reconciliation. The actual cash invoice and account-credit delta remain unavailable.

The generated audio and account diagnostics remain outside Git. Public evidence contains synthetic scripts, sanitized alignment and aggregate measurements. OpenAI and Google comparisons remain price projections; no competitor audio was generated. Human listening is still required before drawing conclusions about pronunciation, Chinese accent, chunk transitions or model preference.
