# Self-Heal

Self-Heal is a task-adaptive agent harness. A trusted supervisor turns observed task limitations into reproducible evaluations, proposes a reusable harness change, tests it against existing and fresh cases, and activates only a validated version.

The first use case is a small Python analyst for structured tables. The editable harness owns its tools and context policy. The protected supervisor owns the oracle, evaluation limits, trace integration, and version decisions.

MongoDB Atlas will hold the structured analyst tables and compact run, case, candidate, evaluation, and version records. A trusted table interface will let each run read only its assigned dataset without exposing Atlas credentials to generated harness code. LangSmith will hold detailed model and tool traces linked to those records. OpenRouter will supply model calls. Candidate code will run in a local Docker container; Git will pin each evaluated version.

**Status:** Phase 1 is implemented and locally tested. The live analyst read a six-row Atlas table through three explicit tools and answered the East available-inventory task correctly. The CLI also accepts ordinary inventory questions and interprets them into the supported task contract. It marks conversational capability refusals with `outcome=unsupported`; Phase 3 will make those observations searchable in LangSmith and Atlas, and Phase 4 will use validated gaps to propose new harness capabilities. The protected oracle, evaluation suite, LangSmith instrumentation, improvement loop, and candidate runner are planned in later phases of [docs/build-plan.md](docs/build-plan.md).

## Run Phase 1

From the repository root, install the locked dependencies and load local credentials from the ignored `.env` file:

```sh
uv sync --extra dev
uv run --env-file .env self-heal seed --fixture evals/analyst/data/small_inventory.json
uv run --env-file .env self-heal run --dataset small-inventory-v1 --question "How many available units are in the East warehouse?"
uv run --env-file .env self-heal run --dataset small-inventory-v1 --question "What is the total on-hand inventory in the West warehouse?"
```

The seed command publishes the fixture rows to Atlas once and verifies the stored row count and hash on repeat runs. The questions receive conversational answers: “There are 18 available units in the East warehouse” and “There are 19 on-hand units in the West warehouse.” For an ambiguous or unsupported question, the agent says “I can't answer that with my current capabilities” and exits normally without reading the table. Actual runtime failures still return an error and a nonzero exit code. Add `--json` to a question command to see its outcome, interpreted task, run ID, and resource counts. Question interpretation uses the configured model and counts toward the same run limits. Questions must fit the supported metrics, one optional equality filter, and one optional grouping field. The current Phase 1 CLI does not yet persist runs or upload LangSmith traces; those records begin in Phase 3.

For a reproducible evaluation input, the structured task form remains available:

```sh
uv run --env-file .env self-heal run --dataset small-inventory-v1 --task '{"metric":"available","filter_field":"warehouse","filter_value":"East"}'
```

Structured task runs continue to print JSON with the answer and run metadata.

The base harness registers `inspect_table`, `read_rows`, and `calculate`. A trusted table adapter binds each run to one Atlas dataset and enforces page and byte limits. Its dataset definitions live in `evals/analyst/data/`; the runtime table rows are read from Atlas. The editable harness receives no connection string through its tool interface. Generated code isolation is added in Phase 4.

The planned Phase 2 stress question asks for available inventory grouped by warehouse over a deterministic 512-row Atlas dataset. Its task definition is in `evals/analyst/data/bulk_task.json`; Phase 2 will generate and grade the rows.

See [SETUP.md](SETUP.md) for account and environment setup.
