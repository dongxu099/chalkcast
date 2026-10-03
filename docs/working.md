# Working record

## Changelog

### 2026-10-03
- Created an independent public-safe project skeleton.
- Chose a declarative renderer and server-side credentials.
- Implemented CLI, local Studio, timestamp narration, estimated cost comparison and an agent skill.
- Verified 28 offline tests, Ruff, skill metadata and a real 19.625-second FFmpeg render.
- Verified desktop/mobile Studio flows and a live arbitrary-topic planner request.
- Independently reviewed and fixed caption bounds, same-job cache cost accounting, failure checkpoints and run isolation.
- Kept ElevenLabs live speech and subjective quality evaluation explicitly pending because no key was available.

## Lessons Learned
- Price comparisons must state model, billing unit, plan and utilization.
- Timing alignment measures synchronization; it does not verify pronunciation.
- Successful provider responses need a checkpoint before local validation or rendering can fail.
- Use fresh artifact folders and share only the audio cache between runs.
