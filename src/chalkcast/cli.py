import json
import os
from pathlib import Path

import typer
import uvicorn

from .costs import estimate as project_cost
from .pipeline import run
from .planner import plan as make_plan
from .schema import RenderOptions, Storyboard

app = typer.Typer(no_args_is_help=True, help="Narrated explainers with inspectable timing and cost.")


def load(path):
    return Storyboard.model_validate_json(path.read_text())


@app.command()
def studio(port: int = 7860, output: Path = Path("output"), keychain: bool = False):
    """Open the local Studio at http://127.0.0.1:7860."""
    from .server import create_app
    if keychain:
        from .credentials import load_keychain
        load_keychain()
    uvicorn.run(create_app(output), host="127.0.0.1", port=port)


@app.command()
def doctor():
    """Check dependencies and credential availability without printing keys."""
    import imageio_ffmpeg
    info = {"encoder": Path(imageio_ffmpeg.get_ffmpeg_exe()).is_file(),
            "keys": {k: bool(os.environ.get(k) and not os.environ[k].startswith("replace-"))
                     for k in ["ELEVENLABS_API_KEY", "OPENAI_API_KEY", "PLANNER_API_KEY"]}}
    typer.echo(json.dumps(info, indent=2))


@app.command()
def plan(topic: str, output: Path = Path("output/storyboard.json"),
         audience: str = "curious beginners", language: str = "en"):
    """Draft arbitrary topics with an OpenAI-compatible planner; review before narration."""
    try:
        board = make_plan(topic, audience, language, output.with_suffix(".usage.json"))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(board.model_dump_json(indent=2))
        typer.echo(str(output))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def estimate(storyboard: Path, model: str = "eleven_flash_v2_5", price_per_1k_characters: float | None = None):
    """Project narration costs using a dated official-price snapshot."""
    typer.echo(json.dumps(project_cost(load(storyboard), model, price_per_1k_characters), indent=2))


@app.command()
def render(storyboard: Path, output: Path = Path("output/demo"), provider: str = "silent",
           model: str = "eleven_flash_v2_5", voice: str = "JBFqnCBsd6RMkjVDRZzb",
           max_cost_usd: float = 1.0, max_characters: int = 10000,
           price_per_1k_characters: float | None = None, audio_only: bool = False):
    """Generate video, captions and a per-request receipt. Silent narration has no speech charge."""
    try:
        options = RenderOptions(provider=provider, model_id=model, voice_id=voice, max_cost_usd=max_cost_usd,
                                max_characters=max_characters, price_per_1k_characters=price_per_1k_characters,
                                render=not audio_only)
        usage_path = storyboard.with_suffix(".usage.json")
        result = run(load(storyboard), options, output.resolve(), output.resolve().parent / ".cache", typer.echo,
                     planner_usage_path=usage_path if usage_path.is_file() else None)
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def benchmark(storyboard: Path, output: Path = Path("output/benchmark"),
              models: str = "eleven_flash_v2_5,eleven_multilingual_v2", voice: str = "JBFqnCBsd6RMkjVDRZzb",
              max_cost_usd: float = 1.0):
    """Run the same script through several ElevenLabs models; store measured audio and reports."""
    board = load(storyboard)
    selected = models.split(",")
    if len(selected) > 4 or any(m not in {"eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2"}
                                for m in selected):
        raise typer.BadParameter("Select at most four supported timestamp models.")
    total = sum(project_cost(board, m)["estimated_usd"] for m in selected)
    if total > max_cost_usd:
        raise typer.BadParameter(f"Whole benchmark estimate ${total:.4f} exceeds the configured budget.")
    results = []
    for model in selected:
        options = RenderOptions(provider="elevenlabs", model_id=model, voice_id=voice,
                                max_cost_usd=max_cost_usd, render=False)
        result = run(board, options, output / model, output / ".cache", typer.echo)
        results.append(result)
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    typer.echo(str(output / "comparison.json"))
