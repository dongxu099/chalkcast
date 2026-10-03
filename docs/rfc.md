# Declarative storyboards and measured narration

The planner emits validated JSON. A scene has title, narration and a visual drawn by trusted Pillow code. The renderer streams frames to bundled FFmpeg. Audio sets scene duration; timestamp alignment sets subtitle timing. Generated code never executes.

ElevenLabs uses `/v1/text-to-speech/{voice_id}/with-timestamps`, scene context and a content-addressed cache. JSON audio and alignment are persisted only in ignored output folders. API reports preserve provider character-cost separately from estimated USD. A monthly subscription and a single generation have different cash-flow implications.

The Studio serves on loopback. Jobs run in a bounded background worker, with one active job per process. API credentials stay server-side in environment variables. This is a personal local tool; internet deployment requires authentication and an actual job queue.

Browser contract: GET `/api/config`; GET `/api/examples`; GET `/api/examples/{name}`; POST `/api/plan` with `{topic, audience, language}`; GET `/api/planner-usage`; POST `/api/estimate` with `{storyboard, model_id, price_per_1k_characters}`; POST `/api/jobs` with `{storyboard, provider, model_id, voice_id, max_cost_usd, max_characters, price_per_1k_characters, render}`; GET `/api/jobs/{id}`; GET `/artifacts/{id}/{filename}`. Job responses contain `id`, `status`, `stage`, `error`, `report`, and `artifacts` (relative links). API errors use `detail`. Config contains boolean credential availability only.

Budget preflight uses the configured price and uncached input characters. It is a local estimate gate, not a provider-enforced spending cap. Custom voices, legacy accounts, provider-side billing and planner charges require separate account limits. No retry happens automatically after an ambiguous paid request.
