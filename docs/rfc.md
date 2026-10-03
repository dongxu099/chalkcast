# Declarative storyboards and measured narration

The planner emits validated JSON. A scene has title, narration and a visual drawn by trusted Pillow code. The renderer streams frames to bundled FFmpeg. Audio sets scene duration; timestamp alignment sets subtitle timing. Generated code never executes.

ElevenLabs uses `/v1/text-to-speech/{voice_id}/with-timestamps`, scene context and a content-addressed cache. JSON audio and alignment are persisted only in ignored output folders. API reports distinguish observed billing headers from local estimates and subscription allocation from overage.

The Studio serves on loopback. Jobs run in a bounded background worker, with one active job per process. API credentials stay server-side in environment variables. This is a personal local tool; internet deployment requires authentication and an actual job queue.

Browser contract: GET `/api/config`; GET `/api/examples`; GET `/api/examples/{name}`; POST `/api/plan` with `{topic, audience, language}`; POST `/api/estimate` with `{storyboard, model_id, rate_per_1k_credits}`; POST `/api/jobs` with `{storyboard, provider, model_id, voice_id, max_credits, rate_per_1k_credits, render}`; GET `/api/jobs/{id}`; GET `/artifacts/{id}/{filename}`. Job responses contain `id`, `status`, `stage`, `error`, `report`, and `artifacts` (relative links). API errors use `detail`. Config contains boolean credential availability only.
