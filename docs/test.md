# Verification

Offline tests cover schema bounds, path safety, caption timing, preflight credit limits, cache reuse, API error handling and mocked provider contracts. Test rendering through the real bundled FFmpeg and inspect a video frame and container metadata. Optional real narration requires an injected key and a credit ceiling. No live request runs in CI.

Human evaluation compares identical scripts and voices where possible: naturalness, equations, acronyms, English/Chinese, chunk transitions and subtitle accuracy. A single generation cannot support a population-level quality ranking.
