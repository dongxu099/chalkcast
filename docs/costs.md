# Compare the same script, then compare the billing units

ChalkCast estimates narration from the exact submitted text. A 5,000-character script projects to **$0.20 with ElevenLabs Flash** or **$0.40 with Multilingual v2** at the current API list rates. These amounts describe consumed service value. A subscription with unused included balance can make the immediate extra cash charge zero. Prices below were checked against live official pages on 2026-10-03.

| Provider/model | List rate | 5,000 input characters | Implemented live adapter |
|---|---:|---:|---|
| ElevenLabs Flash/Turbo v2.5 | $0.04 / 1K characters | $0.20 | Yes |
| ElevenLabs Multilingual v2 | $0.08 / 1K characters | $0.40 | Yes |
| ElevenLabs v3 | $0.08 / 1K characters | $0.40 | Cost projection only |
| OpenAI tts-1 | $15 / 1M characters | $0.075 | Yes, approximate caption timing |
| Google Neural2 | $16 / 1M characters | $0.08 | Cost projection only |
| Google Chirp 3 HD | $30 / 1M characters | $0.15 | Cost projection only |
| OpenAI gpt-4o-mini-tts | $0.60 / 1M text input tokens + $12 / 1M audio output tokens | Requires token counts | Cost formula only |

Sources: [ElevenLabs API pricing](https://elevenlabs.io/pricing/api), [OpenAI tts-1](https://developers.openai.com/api/docs/models/tts-1), [OpenAI mini-tts](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts), [Google TTS pricing](https://cloud.google.com/text-to-speech/pricing). Google lists a monthly first-million-character allowance for Neural2 and Chirp 3 HD. Free allowance depends on remaining monthly SKU usage; it is not a fresh allowance for each video.

## Account mode changes the cash calculation

Current ElevenLabs API plans use USD pricing. Legacy accounts may need to select **Manage subscription → Switch to new pricing**; an upgrade also migrates the account. ElevenCreative's credits are a different product billing scheme. Confirm the account mode before applying these rates. [Official migration notice](https://elevenlabs.io/blog/weve-lowered-api-agents-pricing-and-introduced-pay-as-you-go).

For one model and no other product usage:

```text
consumed value = newly generated characters × USD per 1K characters / 1000
monthly cash ≈ plan fee + max(0, monthly characters − included characters) × rate
```

The monthly formula assumes overage is enabled. Creator lists a regular $22/month, with 275K Multilingual or 550K Flash equivalent characters. These are alternatives representing the same included value. They are not additive allowances. Custom library voices, taxes, promotions and other products may alter the bill. [Plan table](https://elevenlabs.io/pricing/api).

## Each report separates measurements from estimates

`provider_character_cost` preserves the API's `character-cost` response header as a number, alongside its raw string. It means provider-reported generation cost in characters. It is **not** a USD invoice or an assumed credit count. Missing headers remain null. [Request stitching documentation](https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/request-stitching).

`estimated_usd` uses uncached input characters and the selected rate. Audio cache hits add no narration request. Previous/next text participates in the cache key, so editing a scene can also invalidate its neighbors. Regeneration and uncertain failures can consume additional service value.

`max_cost_usd` is an estimated preflight limit. It cannot override provider-side billing. Set an account spending limit as well. A custom rate field lets a user model a legacy account or special voice; the app cannot verify that entered rate.

## A cost receipt for every video request

The Studio result shows **planner tokens**, **ElevenLabs estimated USD**, and **total API cost**. The breakdown includes input/output tokens, planning USD and narration USD. The same data is saved under `request_cost` in downloadable `report.json`.

```text
total API usage value = planner reported USD + newly generated narration estimated USD
```

The total is estimated whenever new narration uses a paid API. It is not a bank-card debit. Monthly plan fees, included balance, discounts, taxes, OpenRouter credit-purchase fees, external authoring and local operating costs are excluded. Local animation/FFmpeg rendering incurs $0 in external API fees and has no LLM token count. ElevenLabs TTS uses characters, not planner tokens.

| Receipt field | Meaning |
|---|---|
| `planner.prompt_tokens`, `completion_tokens`, `total_tokens` | Provider-measured tokens allocated to this request |
| `planner.provider_reported_usd` | Reported OpenRouter API usage value; null if unavailable |
| `elevenlabs_estimated_usd` | New, uncached speech characters × selected USD rate |
| `elevenlabs_provider_reported_usd` | Null for new paid speech: TTS returns no dollar invoice; zero when there is no new speech charge |
| `total_estimated_usd` | Planning plus narration, or null if a required charge is unknown |
| `known_subtotal_usd` | Known portion only, shown separately when the total is incomplete |
| `total_provider_reported_usd` | Available only when every component is reported or zero; usually null for new paid speech |

OpenRouter returns token counts and `usage.cost`; its account credit usage is denominated in USD. Other compatible endpoints may use different cost units, so their dollar amount remains null instead of guessing. No planner list-price lookup or characters-to-tokens conversion is used. Sources: [usage accounting](https://openrouter.ai/docs/guides/guides/usage-accounting), [USD credit-usage schema](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key). Checked on 2026-10-04.

The Studio's `POST /api/plans` returns `{planning_id, storyboard, usage}`. Submit that ID with `POST /api/jobs` to attach the corresponding server-owned receipt. `/api/plan` remains a storyboard-only compatibility endpoint; `/api/planner-usage` remains latest-call telemetry and is never used to attribute a job's cost. Changing examples clears the draft association; reviewing/editing a draft preserves it. Each planner attempt has its own receipt, including rejected generated storyboards. Abandoned drafts are separate requests, outside a later draft's total.

The CLI saves `<storyboard>.usage.json` during `chalkcast plan` and automatically attaches it during `chalkcast render`. Both entry points allocate a draft's fee and tokens to its **first render only**. A durable, atomically written ownership record prevents duplicate allocation across later renders, simultaneous readers and server restarts. Later receipts retain the original usage for inspection, while their incremental planner tokens and cost are zero. Speech cache hits likewise add $0. A manual/example storyboard has no attached in-app planner charge; external authoring costs are outside this receipt.

Receipts are checkpointed before local post-processing. If a later scene or encoder fails, the report retains completed charges. An unconfirmed narration attempt leaves the total unknown and shows a known subtotal; it cannot be treated as free. Planner usage is saved before storyboard validation, so invalid generated JSON does not hide a paid response. Network failures are not automatically retried.


## Update the snapshot before making a proposal

Read the live official page, confirm model and billing unit, then update `src/chalkcast/costs.py` and this document together. Search engines can return an older pricing snapshot: during development, Tavily showed $0.05/$0.10 while the live page showed $0.04/$0.08. Never present a cached price as a current quote. This comparison measures price only; it makes no claim of equal voice quality or feature parity.
