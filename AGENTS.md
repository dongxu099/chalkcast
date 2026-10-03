# ChalkCast contributor contract

Python 3.11+. Install with `uv sync --extra dev`. Use `uv run chalkcast`.
Source lives in `src/chalkcast`, browser assets in `src/chalkcast/static`, fixtures in `examples`, tests in `tests`.
Keep the storyboard declarative. Never execute model-generated Python, HTML, JavaScript or shell commands.
Never store keys in browser storage, request logs, git or artifacts. Credentials come from process environment.
Keep generated artifacts in ignored `output/`. Public fixtures must contain synthetic content.
Update `docs/working.md` for each meaningful change. Commit scaffold, implementation and validation separately.
Before release run Ruff, pytest, a rendered demo and a staged-file privacy scan.
