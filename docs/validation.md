# What has been verified

Checked on 2026-10-03. This document separates a working local pipeline from live provider evaluation.

| Area | Result | Evidence |
|---|---|---|
| Lint | Passed | `ruff check .` |
| Offline tests | 32 passed | `pytest -q`, including a real Chinese-alignment fixture, alignment cache round trip and no-request cache repair |
| Skill metadata | Passed | skill-creator `quick_validate.py` |
| Video encoding | Real FFmpeg render passed | 1280×720 H.264, 24 fps, AAC; 19.625-second quickstart |
| Cache reuse | Passed | Second quickstart run: 2 scene cache hits, $0 narration charge |
| Arbitrary-topic planner | Live OpenRouter request passed | Exponential-backoff draft produced valid scene JSON, then human-reviewed |
| Studio flow | Browser verified | Example → estimate → render → playable MP4 and download links |
| Studio input recovery | Browser verified | Invalid JSON preserves existing story/output and disables render |
| Mobile themes | Browser verified | Narrow viewport, light/dark, no horizontal overflow |
| Failed response recovery | Mocked HTTP verified | Repeated timeout/unusable-success inputs do not send a second request |
| Output isolation | Verified | Nonempty run folders reject new artifacts before paid calls |
| ElevenLabs live speech | Passed | Three fresh Flash and three fresh Multilingual samples; English and Chinese narrated MP4s |
| Chinese captions | Passed after fix | Original Han-character alignment selected when normalized alignment returned pinyin; both scene subtitles match input |
| Live cache reuse | Passed | Unchanged English run: two hits, no HTTP request; older Chinese cache repaired without resynthesis |
| Account billing reconciliation | **Unavailable with current key permissions** | Account/model-list GETs return HTTP 401 `missing_permissions`; TTS requests succeed |
| Competitor live speech | **Not run** | OpenAI adapter tested offline; Google/mini-tts are cost formulas |
| Subjective voice quality | **Not measured** | Requires real generation and listening |

The default test environment reports one upstream Starlette/httpx deprecation warning; the tests pass. It does not indicate a failed API or rendering check.

Prices were checked against live official pages. Search-cache pricing differed from the live ElevenLabs page and was corrected before release. See [cost assumptions](costs.md). The planner's backoff/jitter error was corrected before adding the reviewed public sample; see [evaluation](evaluation.md).

See [live measurements](live-evaluation.md) for sample latencies, raw character-cost telemetry and the $0.09304 total list-price projection. This is not a verified invoice. Audio quality and pronunciation scores remain pending human listening; competitor speech remains untested.

The initial public GitHub CI run passed lint, all then-current offline tests and the Linux FFmpeg render. An explicit mocked OpenAI Speech contract test was subsequently added; it does not constitute a live competitor benchmark. Real provider requests remain local and are excluded from CI.
