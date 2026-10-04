---
name: chalkcast
description: Create narrated geometric explainer videos from topics or reviewed storyboards using the ChalkCast CLI and ElevenLabs. Use for explainer video creation and narration evaluation, not voice cloning or arbitrary cinematic video.
---

# ChalkCast

Deliver a reviewed storyboard, playable MP4, SRT captions and a report of narration timing, caching and estimated cost. Resolve this repository from the workspace's discovery index. Install with `uv sync --extra dev` if needed. The CLI is `uv run chalkcast`; schemas live in `src/chalkcast/schema.py`.

You can author storyboard JSON directly without a second LLM API. Use a bundled example as the contract. Match narration to the audience and language. Explain one idea per scene with chart, bars, flow or plain-text equation visuals. Check facts, units, conditions and illustrative numbers before narrating. Model validation checks rendering bounds, not factual truth.

Use `chalkcast estimate <storyboard>` before a paid render. A narration request requires the user's authorization and an injected `ELEVENLABS_API_KEY`; preserve authorization already given in the conversation. Do not request or print raw keys. Private credential aliases belong in the target workspace's local overlay or secret manager, never this repo.

`chalkcast render <storyboard> --provider elevenlabs --model eleven_flash_v2_5 --max-cost-usd 1 --output output/<name>` generates the outputs. Choose Multilingual v2 when evaluating long-form delivery; benchmark the same reviewed text with `chalkcast benchmark <storyboard>`. Exact quality claims require listening. A silent render proves the visual pipeline only.

Verify that video duration covers narration, captions use provider alignment when available, and report fields separate local USD estimates from raw character-cost. Reuse the same output parent to reuse audio cache. Context changes also invalidate adjacent scene caches. On uncertain network failure, stop and inspect account usage; there is no automatic retry.

For Chinese, normalized alignment can contain pinyin. Preserve Han characters using the original alignment; if a reliable character mapping is unavailable, retain the source text and label timing as estimated. Both alignment forms are saved with new audio cache entries, allowing caption repairs without resynthesis.

Give the requester `report.json` with its `request_cost` receipt: input/output/total planner tokens, reported planner USD, estimated new ElevenLabs USD and total estimated API usage value. The CLI automatically attaches the planning sidecar. A draft fee is allocated once; cached speech and reused drafts add zero incremental cost. Never join a job to shared latest-call telemetry. Unknown charges stay null with a known subtotal. Inspect partial receipts after failures; preserve paid usage before validating generated content. API usage value excludes account subscription cash charges and external authoring/local compute. Verify CLI parameters against help and provider fields/units against their official schema before implementation.

See [cost methodology](../../docs/costs.md) for billing units and [evaluation protocol](../../docs/evaluation.md) for listening and failure tests. Output stays local unless the user authorizes publication.
