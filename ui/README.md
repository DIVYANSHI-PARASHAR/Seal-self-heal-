# Self-Heal local UI

This interface is a local operator surface for the implemented system. It uses the same
trusted execution path as `self-heal run`: an analysis reads only its automatically selected
operator Atlas dataset, records compact run history, and optionally links a verified LangSmith
root trace. Generated evaluation tables are excluded from automatic selection. Once a version
is active, both surfaces execute that pinned commit in Docker.

The single-line question field opens suggested questions on focus. Use arrow keys and Enter
to choose one, or Escape to close the list. Recent runs open a detailed evidence view.

Start it from the repository root after configuring `.env` and materializing a dataset:

```sh
uv run --env-file .env self-heal seed --fixture evals/analyst/data/small_inventory.json
uv run --env-file .env self-heal ui
```

Open [http://127.0.0.1:4173](http://127.0.0.1:4173). The server listens on loopback by default;
use `--host` and `--port` only when an explicitly different local setup is required.

New runs store bounded, redacted snapshots of rows actually read and tool calls actually made.
The evidence view shows those rows by read page, tool arguments and result previews, resource
counts, and LangSmith span metadata when tracing is available. Raw payloads are collapsed.
Older run records without row snapshots explicitly say so; available LangSmith traces can
still supply redacted tool-call details. Capability gaps link to recorded
evaluation cases and candidate diffs when present; correctness and regression status use the
stored selection trials. Candidate proposal, protected evaluation, promotion, and rollback
controls remain CLI operations.
