# Self-Heal local UI

This interface is a local operator surface for the implemented Phase 3 system. It uses the same
trusted `RunExecutor` as `self-heal run`: an analysis reads only its automatically selected
operator Atlas dataset, records compact run history, and optionally links a verified LangSmith
root trace. When a user-facing dataset is available, it is preferred over `eval-` fixtures.

Start it from the repository root after configuring `.env` and materializing a dataset:

```sh
uv run --env-file .env self-heal seed --fixture evals/analyst/data/small_inventory.json
uv run --env-file .env self-heal ui
```

Open [http://127.0.0.1:4173](http://127.0.0.1:4173). The server listens on loopback by default;
use `--host` and `--port` only when an explicitly different local setup is required.

The UI shows only metadata, compact history, resource measurements, and the LangSmith trace link.
It does not expose raw table rows or detailed trace payloads. Candidate proposal, protected
evaluation, and version promotion UI remain Phase 4+ work and are intentionally not represented
as completed functionality.
