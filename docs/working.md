# Working record

## Changelog

### 2026-10-03
- Created an independent public-safe project skeleton.
- Chose a declarative renderer and server-side credentials.
- Implemented CLI, local Studio, timestamp narration, estimated cost comparison and an agent skill.
- Verified 28 offline tests, Ruff, skill metadata and a real 19.625-second FFmpeg render.
- Verified desktop/mobile Studio flows and a live arbitrary-topic planner request.
- Independently reviewed and fixed caption bounds, same-job cache cost accounting, failure checkpoints and run isolation.
- Initially left ElevenLabs live speech pending until a key became available.
- Completed three independent samples per model and real English/Chinese narrated videos; list-price projection including follow-up validation was $0.09304.
- Found normalized Chinese alignment returning pinyin, selected original Han-character alignment, and preserved both forms in cache. Old caption records repair without resynthesis, with estimated timing when raw alignment is unavailable.
- Added four regression tests; 32 offline tests and Ruff pass. Subjective voice quality and live competitor comparisons remain pending.

## Lessons Learned
- Price comparisons must state model, billing unit, plan and utilization.
- Timing alignment measures synchronization; it does not verify pronunciation.
- Successful provider responses need a checkpoint before local validation or rendering can fail.
- Use fresh artifact folders and share only the audio cache between runs.
- A valid TTS key can lack account/model-list read permissions. Inspect the provider's error category before interpreting HTTP 401.
- Normalized text can be phonetic. Check the writing system before turning alignment characters into captions.
