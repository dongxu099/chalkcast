# What has been verified

Checked on 2026-10-03. This document separates a working local pipeline from live provider evaluation.

| Area | Result | Evidence |
|---|---|---|
| Lint | Passed | `ruff check .` |
| Offline tests | 28 passed | `pytest -q` |
| Skill metadata | Passed | skill-creator `quick_validate.py` |
| Video encoding | Real FFmpeg render passed | 1280×720 H.264, 24 fps, AAC; 19.625-second quickstart |
| Cache reuse | Passed | Second quickstart run: 2 scene cache hits, $0 narration charge |
| Arbitrary-topic planner | Live OpenRouter request passed | Exponential-backoff draft produced valid scene JSON, then human-reviewed |
| Studio flow | Browser verified | Example → estimate → render → playable MP4 and download links |
| Studio input recovery | Browser verified | Invalid JSON preserves existing story/output and disables render |
| Mobile themes | Browser verified | Narrow viewport, light/dark, no horizontal overflow |
| Failed response recovery | Mocked HTTP verified | Repeated timeout/unusable-success inputs do not send a second request |
| Output isolation | Verified | Nonempty run folders reject new artifacts before paid calls |
| ElevenLabs live speech | **Not run: API key unavailable** | Timing and audio contracts tested with synthetic HTTP/MP3 fixtures |
| Competitor live speech | **Not run** | OpenAI adapter tested offline; Google/mini-tts are cost formulas |
| Subjective voice quality | **Not measured** | Requires real generation and listening |

The default test environment reports one upstream Starlette/httpx deprecation warning; the tests pass. It does not indicate a failed API or rendering check.

Prices were checked against live official pages. Search-cache pricing differed from the live ElevenLabs page and was corrected before release. See [cost assumptions](costs.md). The planner's backoff/jitter error was corrected before adding the reviewed public sample; see [evaluation](evaluation.md).

To complete the speech evaluation, inject a key and run the short `voice_probe` benchmark, then the English and Chinese examples. Record listening observations and actual response headers. Do not turn mock results into claims of measured provider quality, latency or billing.

The first public GitHub CI run passed lint, all then-current offline tests and the Linux FFmpeg render. The final validation update adds an explicit mocked OpenAI Speech contract test; it does not constitute a live competitor benchmark.
