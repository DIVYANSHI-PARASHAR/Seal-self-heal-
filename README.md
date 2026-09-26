# Self-Heal

Self-Heal is a task-adaptive agent harness. A trusted supervisor turns observed task limitations into reproducible evaluations, proposes a reusable harness change, tests it against existing and fresh cases, and activates only a validated version.

The first use case is a small Python analyst for structured tables. The editable harness owns its tools and context policy. The protected supervisor owns the oracle, evaluation limits, trace integration, and version decisions.

MongoDB Atlas will hold the structured analyst tables and compact run, case, candidate, evaluation, and version records. A trusted table interface will let each run read only its assigned dataset without exposing Atlas credentials to generated harness code. LangSmith will hold detailed model and tool traces linked to those records. OpenRouter will supply model calls. Candidate code will run in a local Docker container; Git will pin each evaluated version.

**Status:** Phases 1 through 3 are implemented and locally tested. The base analyst reads Atlas-backed tables through three explicit tools and accepts ordinary inventory questions. The evaluator outside `harness/` generates deterministic datasets, calculates exact answers independently, and verifies the current harness against fixed scenarios. Each supervised run now has a compact Atlas history record and, when LangSmith tracing is configured, a linked root trace with nested model and tool spans. Explicit conversational refusals are stored as `outcome=unsupported` and `limitation_kind=capability_gap`, ready for Phase 4 to turn independently gradable gaps into reusable harness capabilities.

## Run Phases 1 through 3

From the repository root, install the locked dependencies and load local credentials from the ignored `.env` file:

```sh
uv sync --extra dev
uv run --env-file .env self-heal seed --fixture evals/analyst/data/small_inventory.json
uv run --env-file .env self-heal run --dataset small-inventory-v1 --question "How many available units are in the East warehouse?"
uv run --env-file .env self-heal run --dataset small-inventory-v1 --question "What is the total on-hand inventory in the West warehouse?"
```

The seed command publishes the fixture rows to Atlas once and verifies the stored row count and hash on repeat runs. The questions receive conversational answers: “There are 18 available units in the East warehouse” and “There are 19 on-hand units in the West warehouse.” For an ambiguous or unsupported question, the agent says “I can't answer that with my current capabilities” and exits normally without reading the table. Actual runtime failures still return an error and a nonzero exit code. Add `--json` to a question command to see its outcome, interpreted task, run ID, resource counts, compact trace link or ID, and Atlas history status. Question interpretation uses the configured model and counts toward the same run limits. Questions must fit the supported metrics, one optional equality filter, and one optional grouping field.

For a reproducible evaluation input, the structured task form remains available:

```sh
uv run --env-file .env self-heal run --dataset small-inventory-v1 --task '{"metric":"available","filter_field":"warehouse","filter_value":"East"}'
```

Structured task runs continue to print JSON with the answer and run metadata.

## Inspect Phase 3 evidence

With `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT` set, every `run` and `eval run` command creates a LangSmith root trace using the same UUID as its Atlas `runs` record. The CLI returns only compact evidence; inspect detailed model and tool activity through the returned LangSmith link. If trace upload or immediate retrieval cannot be verified, `trace.status` is `incomplete` while the independently measured agent result remains intact.

Use Atlas-backed history retrieval to find requests that the current harness explicitly knows it cannot answer:

```sh
uv run --env-file .env self-heal run --dataset small-inventory-v1 --question "What is total revenue?" --json
uv run --env-file .env self-heal history capability-gaps --task-family inventory-totals
```

The gap list includes the original question, dataset ID and content hash, source/config/model identity, independent resource measurements, and LangSmith root trace reference. It contains no copied table rows or full trace payloads. Rows remain in `analyst_datasets` and `analyst_rows`; detailed trace payloads remain in LangSmith after redaction. `self-heal history run --run-id <id>` returns one compact record, and `self-heal history candidates --task-family inventory-totals` is ready for Phase 4's proposal history.

The base harness registers `inspect_table`, `read_rows`, and `calculate`. A trusted table adapter binds each run to one Atlas dataset and enforces page and byte limits. Its dataset definitions live in `evals/analyst/data/`; the runtime table rows are read from Atlas. The editable harness receives no connection string through its tool interface. Generated code isolation is added in Phase 4.

## Run the protected baseline evaluation

Phase 2 declares one small success, one zero-match edge case, and one 512-row grouped stress case in `evals/analyst/scenarios.yaml`. Materialize their valid datasets, then run either baseline check:

```sh
uv run --env-file .env self-heal eval materialize
uv run --env-file .env self-heal eval run --scenario small-east-available
uv run --env-file .env self-heal eval run --scenario bulk-warehouse-available
```

The small case must pass. The bulk case must report `model_call_budget_exhausted`: each model tool call can read at most four rows, so the base harness cannot inspect all 512 rows inside its eight model calls. The command exits successfully when the observed result matches the declared baseline expectation. Invalid-row scenarios are deliberately skipped during materialization and are tested locally to ensure Atlas rejects them.

Evaluation runs use the same Phase 3 supervisor path. They persist a frozen case reference with exposure history, a linked run, and an evaluation record containing the independent pass or violation outcome. The compact command output includes its run and trace IDs; expected answers and table rows are not uploaded as trace payloads.

See [SETUP.md](SETUP.md) for account and environment setup.
