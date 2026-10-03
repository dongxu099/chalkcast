"""Loopback-only Studio. No browser-side credentials or generated code execution."""
import json
import os
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .costs import estimate
from .pipeline import run
from .planner import plan
from .schema import JobRequest, Storyboard

BASE = Path(__file__).parent
EXAMPLES = BASE / "examples"


class PlanRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    audience: str = Field(default="curious beginners", max_length=200)
    language: str = Field(default="en", min_length=2, max_length=16)


class EstimateRequest(BaseModel):
    storyboard: Storyboard
    model_id: str = "eleven_flash_v2_5"
    price_per_1k_characters: float | None = Field(default=None, ge=0, le=100)


def create_app(output: Path = Path("output")):
    app = FastAPI(title="ChalkCast", docs_url="/api/docs", redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])
    output = output.resolve()
    jobs, lock, pool = {}, threading.Lock(), ThreadPoolExecutor(max_workers=1)

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and request.method != "GET":
            parsed = urlparse(origin)
            if parsed.netloc != request.headers.get("host") or parsed.scheme != request.url.scheme:
                return JSONResponse({"detail": "Use the Studio from its own loopback origin."}, status_code=403)
        if int(request.headers.get("content-length", "0")) > 256000:
            return JSONResponse({"detail": "Request body too large."}, status_code=413)
        return await call_next(request)

    @app.get("/")
    def home():
        return FileResponse(BASE / "static" / "index.html")

    @app.get("/api/config")
    def config():
        def configured(name):
            value = os.environ.get(name, "")
            return bool(value and not value.startswith("replace-"))
        return {"elevenlabs_available": configured("ELEVENLABS_API_KEY"),
                "openai_available": configured("OPENAI_API_KEY"),
                "planner_available": configured("PLANNER_API_KEY") or configured("OPENAI_API_KEY"),
                "default_voice_id": os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"),
                "default_model_id": "eleven_flash_v2_5"}

    @app.get("/api/examples")
    def examples():
        return [{"name": p.stem, "title": json.loads(p.read_text())["title"]}
                for p in sorted(EXAMPLES.glob("*.json"))]

    @app.get("/api/examples/{name}")
    def example(name: str):
        if not re.fullmatch(r"[a-z0-9_-]{1,60}", name):
            raise HTTPException(404, "Example not found")
        path = EXAMPLES / f"{name}.json"
        if not path.is_file():
            raise HTTPException(404, "Example not found")
        return json.loads(path.read_text())

    @app.post("/api/plan")
    def make_plan(body: PlanRequest):
        try:
            return plan(body.topic, body.audience, body.language, output / "planner_usage.json")
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/estimate")
    def make_estimate(body: EstimateRequest):
        try:
            return estimate(body.storyboard, body.model_id, body.price_per_1k_characters)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/planner-usage")
    def planner_usage():
        path = output / "planner_usage.json"
        return json.loads(path.read_text()) if path.exists() else {"note": "No planner request in this session."}

    def execute(job_id, body):
        def notify(stage):
            with lock:
                jobs[job_id]["stage"] = stage
        try:
            with lock:
                jobs[job_id]["status"] = "running"
            result = run(body.storyboard, body, output / job_id, output / ".cache", notify)
            links = {"storyboard": "storyboard.json", "report": "report.json", "subtitles": "subtitles.srt"}
            if body.render:
                links.update(video="video.mp4", narration="narration.m4a")
            with lock:
                jobs[job_id].update(status="completed", report=result,
                                    artifacts={k: f"/artifacts/{job_id}/{v}" for k, v in links.items()})
        except (ValueError, OSError) as exc:
            with lock:
                jobs[job_id].update(status="failed", error=str(exc), stage="Failed; cached audio is preserved")
        except Exception:  # noqa: BLE001 - worker boundary must redact provider request details.
            # Never echo exception objects containing credentials, URLs or request bodies.
            with lock:
                jobs[job_id].update(status="failed", error="Job failed. Inspect local artifacts and encoder.log.")

    @app.post("/api/jobs", status_code=202)
    def submit(body: JobRequest):
        with lock:
            if any(j["status"] in {"queued", "running"} for j in jobs.values()):
                raise HTTPException(409, "Another job is running. Wait for it to finish.")
            if len(jobs) > 100:
                jobs.pop(next(iter(jobs)))
            job_id = uuid.uuid4().hex
            jobs[job_id] = {"id": job_id, "status": "queued", "stage": "Queued", "error": None,
                            "report": None, "artifacts": {}}
            result = dict(jobs[job_id])
        pool.submit(execute, job_id, body)
        return result

    @app.get("/api/jobs/{job_id}")
    def status(job_id: str):
        with lock:
            if job_id not in jobs:
                raise HTTPException(404, "Job not found; statuses are scoped to this server session.")
            return dict(jobs[job_id])

    @app.get("/artifacts/{job_id}/{filename}")
    def artifact(job_id: str, filename: str):
        allowed = {"video.mp4", "narration.m4a", "subtitles.srt", "report.json", "storyboard.json"}
        if not re.fullmatch(r"[0-9a-f]{32}", job_id) or filename not in allowed:
            raise HTTPException(404, "Artifact not found")
        path = output / job_id / filename
        if not path.is_file():
            raise HTTPException(404, "Artifact not found")
        return FileResponse(path)

    return app
