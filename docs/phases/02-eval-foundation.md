# Phase 2 — Protected evaluation foundation

**Outcome:** the project has an independent answer source and a small regression bank before any self-improvement begins.

**Status:** Implemented. The evaluator lives outside `harness/`; Phase 4 adds the Docker boundary that prevents generated candidates from importing its oracle or scenario code.

## Build

1. Define the supported analyst task family in `config/analyst.yaml`: permitted equality filters, grouping by a low-cardinality field such as warehouse or category, numeric sums/differences, output ordering, and invalid-input behavior. Keep the contract narrow enough for an exact reference calculation.
2. Implement `evals/analyst/generator.py` to create deterministic tables and structured task cases from scenario parameters. Store disclosed development case definitions in `evals/analyst/scenarios.yaml`. Generate variable row order, group count, values, filters, empty results, and invalid rows. Materialize each generated table through the trusted Atlas adapter as an immutable dataset; record its dataset ID, seed, row count, and content hash. Repeated materialization of the same definition must resolve to identical rows rather than silently overwrite them.
3. Implement `evals/analyst/oracle.py` as the protected calculation of expected answers. Check it against hand-worked examples in `tests/test_scenarios.py`. The candidate harness may use the same input data, but it cannot import or see the oracle or reference outputs.
4. Implement the initial case runner in `src/self_heal/evaluation.py`. It launches the fixed working-tree harness with a controlled natural-language question and an Atlas dataset ID bound to a fresh run-scoped table-access interface, collects the structured answer, compares it with the oracle, and measures step/tool/time and data-read budgets outside `harness/`. It retains every trial in the evaluator process; durable Atlas trial history begins in Phase 3.
5. Establish three disclosed baseline cases: the Phase 1 small success, an edge case, and a generated 512-row dataset for the `bulk-warehouse-available` task definition. Verify that the initial harness fails the larger supported task for a known correctness or budget reason. Freeze the failing case before asking a model for a patch.
6. Define evaluation semantics for `outcome=unsupported`: it is a normal conversational response for a user, but it fails an eval when the frozen requirement expects an answer. Include a scripted unsupported-question case and preserve the original natural-language request alongside the validated task or proposed new capability. Do not count a no-match total of zero, malformed model output, or infrastructure failure as a capability gap.

## Configuration

Use the fixed agent model from Phase 1 for live comparisons. Fixture seeds, evaluator limits, and expected answers belong in protected configuration or evaluator storage, not in the editable `harness/` directory or candidate-visible Atlas rows. Keep private dataset IDs and metadata inaccessible through the table-access interface. Set the Docker runner image name in `.env`; candidate execution with this boundary is wired in Phase 4.

## Completion checks

- Hand-checked oracle examples pass; repeated generation from the same parameters yields identical Atlas rows, content hashes, and answers.
- A run can read only its assigned Atlas dataset; the oracle and other datasets are unavailable through its table interface.
- The initial harness passes the small case and reliably fails the bulk case under the declared limits. The evaluator reports the violated requirement, not just whether an exception occurred.
- A deliberately wrong answer, budget increase, or missing output is rejected by the evaluator. Old successful cases remain part of the regression bank.
- The evaluator distinguishes an explicit unsupported response from an error and can grade it against a declared answerable requirement without treating the polite response as task success.

**Phase deliverables:** `evals/analyst/{generator,oracle,scenarios.yaml}`, `src/self_heal/evaluation.py`, `tests/{test_scenarios,test_evaluation}.py`, and the evaluation fields of `config/analyst.yaml`.
