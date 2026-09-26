# Self-Heal local UI

This interface is a local operator surface for the implemented system. It uses the same
trusted execution path as `self-heal run`: an analysis reads only its automatically selected
operator Atlas dataset, records compact run history, and optionally links a verified LangSmith
root trace. Generated evaluation tables are excluded from automatic selection. Once a version
is active, both surfaces execute that pinned commit in Docker.

The single page keeps the analysis form at the top. A new or selected historical run shows its
result and run details below the form, with recent runs and capability gaps farther down.

Start it from the repository root after configuring `.env` and materializing a dataset:

```sh
uv run --env-file .env self-heal seed --fixture evals/analyst/data/small_inventory.json
uv run --env-file .env self-heal ui
```

Open [http://127.0.0.1:4173](http://127.0.0.1:4173). The server listens on loopback by default;
use `--host` and `--port` only when an explicitly different local setup is required.

The UI shows only metadata, compact history, resource measurements, and the LangSmith trace link.
It does not expose raw table rows or detailed trace payloads. Candidate proposal, protected
evaluation and version promotion controls remain CLI operations.
