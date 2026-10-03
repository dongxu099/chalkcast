# Learn from a controlled narration experiment

Use one reviewed script, the same voice and unchanged settings to compare Flash v2.5 and Multilingual v2. Save audio and reports before listening. Varying the text, voice and model together prevents useful attribution. The bundled `voice_probe.json` tests acronyms, numbers and spoken mathematics; `zh_cache.json` adds Chinese narration.

```bash
uv run chalkcast benchmark examples/voice_probe.json --max-cost-usd 0.10
uv run chalkcast render examples/bayes.json --provider elevenlabs --model eleven_multilingual_v2
```

Each benchmark model gets a folder containing per-scene MP3, SRT and report. Open `scene_01.mp3` in any local player. `comparison.json` contains all reports. The benchmark preflights the whole model set before sending any generation request.

| Question | Evidence to collect | What it tells you |
|---|---|---|
| Does speech sound natural? | Blind listening, 1–5 score, written observation | Human preference on this script |
| Are API, JSON, CPU and equations pronounced correctly? | Listen, mark exact phrase and error | Whether rewriting or a dictionary is needed |
| Are Chinese phrasing and tone acceptable? | Native-speaker listening | Suitability for this audience |
| Is a scene transition abrupt? | Listen to the stitched narration.m4a | Context and chunk-boundary behavior |
| Do captions follow the spoken words? | Play MP4, inspect returned normalized alignment | Synchronization, not factual correctness |
| How long did generation take? | Segment wall_seconds and report narration_wall_seconds | End-to-end full-response delay |
| How much did it consume? | Provider header, local projection, account usage | Difference between service use and cash bill |
| Does repeat rendering avoid API calls? | Repeat unchanged input and inspect cache_hits | Cost and recovery behavior |

Run at least three independent generations before treating latency differences as more than a sample. Cache hits must be excluded from provider latency analysis. ChalkCast measures the entire response; it does not measure streaming time to first audio byte. Vendor low-latency claims use a different metric.

## Capabilities worth demonstrating

ElevenLabs returns character alignment with narration, allowing the animation and captions to follow actual speech. Normalized alignment handles spoken expansion of numbers. Model choice supports a quality/latency/cost tradeoff, and neighboring text can improve continuity across chunks. These are documented capabilities; exact results require live evaluation. [Timing endpoint](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps), [model guide](https://elevenlabs.io/docs/overview/models), [stitching guide](https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/request-stitching).

## Friction and limitations to investigate

- Alignment can be missing. The report labels proportional caption timing as an estimate.
- Speech is nondeterministic. Similar settings do not guarantee identical delivery.
- Chunking makes recovery cheaper but can change prosody at boundaries.
- v3 does not support request stitching. It is included in the cost table but excluded from this release's live adapter.
- Billing mode and some custom voice rates require account-level verification.
- The timestamp endpoint buffers a complete JSON/base64 response. A real-time voice agent needs a streaming design and different measurements.

Offline tests exercise missing alignment and cache recovery. Pronunciation, prosody and voice quality remain unmeasured until live narration. These are evaluation questions, not measured vendor defects. OpenAI and Google price projections do not constitute live quality benchmarks.

## Factual review is a separate acceptance step

The planner successfully produced an exponential-backoff storyboard during development. It also claimed backoff alone breaks synchronized retries. Human review corrected this: backoff lowers retry frequency; jitter breaks synchronization. Valid JSON and fluent narration do not establish truth. Keep source review before the paid narration step.

## A useful solution-engineering demo

Start with the customer's audience, language, expected monthly video count and latency requirement. Show a reviewed storyboard and run one short generation. Explain the report, play the audio, change one scene and show cache reuse. Then discuss production additions: authenticated access, durable queues, observability, provider spending limits and editorial ownership. This local app intentionally exposes those integration choices without claiming production readiness.
