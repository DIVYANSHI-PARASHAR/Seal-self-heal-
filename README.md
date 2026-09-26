# Self-Heal

Self-Heal is a task-adaptive agent harness. A trusted supervisor turns observed task limitations into reproducible evaluations, proposes a reusable harness change, tests it against existing and fresh cases, and activates only a validated version.

The first use case is a small Python analyst for structured tables. The editable harness owns its tools and context policy. The protected supervisor owns the oracle, evaluation limits, trace integration, and version decisions.

MongoDB Atlas holds structured analyst tables and compact run, case, candidate, evaluation, gap, and version records. A trusted table interface lets each run read only its assigned dataset without exposing Atlas credentials to generated harness code. LangSmith holds detailed model and tool traces. OpenRouter supplies model calls. Candidate code runs in a local Docker container; Git pins each evaluated version.

**Status:** Phases 1–5 and the Phase 6 reserve/assessment controls are implemented. The Phase 4–5 control flow, selection gates, promotion, and Docker bridge pass local tests, including a real Docker run. A live bulk failure was reproduced and sent through the configured evolution model. Its recovered proposal was rejected after 28 recorded selection trials because it failed correctness and regression gates. No candidate was activated, so there is no live final-assessment result yet.

## Use the local operator UI

The operator UI uses the same trusted execution path as the CLI. It automatically chooses a ready
operator dataset and has separate Ask, Runs, Evaluations, and Versions pages. The question field stays
at the top of every page. A run detail shows its answer, resources, Atlas rows actually read, tool
calls, timeline, verified LangSmith span metadata when available, and candidate checks for capability
gaps. The evaluation page includes stored selection/baseline trials and final assessments, labeled by
role. Once a version
is active, new UI and CLI runs use that pinned commit through the Docker runner. Evolution decisions
are available through the CLI and Atlas history.

Materialize a dataset, then start the loopback-only server:

```sh
uv run --env-file .env self-heal seed --fixture evals/analyst/data/small_inventory.json
uv run --env-file .env self-heal seed-logistics
uv run --env-file .env self-heal ui
```

Open [http://127.0.0.1:4173](http://127.0.0.1:4173). Use `self-heal ui --help` for an explicit
host or port override. The UI exposes bounded redacted snapshots of rows read during each run, not
complete datasets or full LangSmith trace contents.

The browser selects the logistics bundle by default when available. If it is not seeded yet, use
**Load logistics demo** in the UI, or run `self-heal seed-logistics` before starting the server.
The public bundle contains 8 customers, 3 warehouses, and 74 shipments. The current baseline
recognizes “How many customers sent more than 15 shipments from warehouse 3 yesterday?” and records
an honest capability gap against that bundle; it does not yet return the oracle answer. The source
selector can switch back to an inventory table for the existing inventory questions.

## Phase 6: final assessment and lineage

Reserve fresh cases **before** evolving a candidate. Put the private manifest outside the checkout,
for example in a protected temporary directory; it is created with owner-only permissions. The
reserve command publishes two immutable `final-` Atlas datasets and stores their IDs, hashes, tasks,
and oracle hashes in the manifest. Candidate selection rejects `final-` datasets, and the operator UI
never selects them for ordinary questions.

```sh
uv run --env-file .env self-heal final reserve --manifest /tmp/self-heal-final-2026.json
# Run the normal incident → evolve → selection → promotion cycle.
uv run --env-file .env self-heal final assess --manifest /tmp/self-heal-final-2026.json
uv run --env-file .env self-heal history final
uv run --env-file .env self-heal history lineage --run-id <incident-run-id>
```

`final assess` requires an accepted active commit and the same config, model identity, and Docker
image as selection. It claims each case in Atlas before the run, so a used case cannot be retried as
untouched. Results retain individual correctness, resources, trace ID, and failure details in a
separate `final_assessments` collection. A failed final case is consumed; reserve a new manifest for
any later final claim. `history lineage` links the incident, capability gap, observed evaluation
cases, exact candidate diff/commit, selection trials, active commit, and final records. A successful
final result can only be reported after these commands actually run against an accepted version.

## Run the analyst

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

The gap list includes the original question, dataset ID and content hash, source/config/model identity, independent resource measurements, and LangSmith root trace reference. It contains no copied table rows or full trace payloads. Rows remain in `analyst_datasets` and `analyst_rows`; detailed trace payloads remain in LangSmith after redaction. `self-heal history run --run-id <id>` returns one compact record, and `self-heal history candidates --task-family inventory-totals` shows proposal history.

The base harness registers `inspect_table`, `read_rows`, and `calculate`. A trusted table adapter binds each run to one Atlas dataset and enforces page and byte limits. Its dataset definitions live in `evals/analyst/data/`; runtime rows are read from Atlas. Generated code receives no connection string or protected oracle files.

## Logistics capability foundation

The protected logistics expansion is additive: `logistics_datasets`,
`logistics_customers`, `logistics_warehouses`, and `logistics_shipments` hold
immutable related-data bundles alongside the existing inventory collections.
`evals/logistics/generator.py` defines the synthetic 74-shipment public
incident fixture; its independent oracle returns `{"value": 2}` for “How
many customers sent more than 15 shipments from warehouse 3 yesterday?”

The current baseline deliberately refuses that reviewed request before any
model or data read, with a `capability_gap` and a structured
`shipment_customer_threshold` request. This preserves the intended evolution
signal. The protected logistics session itself exposes only catalog/relation
inspection and filter-bound, cursor-bound shipment pages; it does not expose
database credentials, collection names, or arbitrary queries.

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

## Evolve and activate a harness version

Build the isolated image once, then run an observed incident by its Atlas run ID:

```sh
uv run --env-file .env self-heal runner build
uv run --env-file .env self-heal evolve --run-id <completed-run-id>
uv run --env-file .env self-heal evolve --run-id <completed-run-id> --rescreen-candidate <candidate-id>
uv run --env-file .env self-heal history active
```

`evolve` reads the linked LangSmith trace, sends a redacted incident and editable harness source to the configured `OPENROUTER_EVOLUTION_MODEL`, and writes durable Atlas gap, case, candidate, trial, and version records. It accepts only a clean, pinned source commit and a verified dataset. An out-of-contract request remains in `capability_gaps` with the needed contract, data-access, and oracle extension. A gradable failure must reproduce on the original request and a new frozen case before a proposed patch is applied.

Use `--rescreen-candidate` only when a screening implementation bug rejected a stored patch before it received a candidate commit. It reuses the exact stored diff and attempt number, then records a linked selection; it does not grant another model proposal.

The model produces a unified diff limited to `harness/*.py`. The supervisor screens and commits it in an ignored Git worktree. Baseline and candidate run in the same image with only the harness directory mounted read-only. The container has no network, Atlas/OpenRouter/LangSmith credentials, table snapshots, expected answers, or oracle. Model and bounded table requests travel through the host bridge. The host measures calls, tokens, pages, bytes, and time and grades exact answers. Selection freezes the original, generated, regression, private validation, and unrelated refusal cases before trials; it retains every trial and requires repeated success on the original and fresh variations. Promotion checks the exact tested commit and environment, then changes the active version only if its parent still matches. Subsequent `run` commands use that commit. Roll back to a retained version with:

```sh
uv run --env-file .env self-heal rollback --expected-active <commit> --commit <prior-commit> --reason "reason"
```

Selection thresholds and attempt limits live in [config/analyst.yaml](config/analyst.yaml). The Docker image build context is restricted to `runner_support/`; candidate worktrees stay under ignored `.self-heal/`.
