# Phase 2 — Protected evaluation foundation

**Outcome:** the project has an independent answer source and a small regression bank before any self-improvement begins.

## Build

1. Define the supported analyst task family in `config/analyst.yaml`: permitted equality filters, grouping by a low-cardinality field such as warehouse or category, numeric sums/differences, output ordering, and invalid-input behavior. Keep the contract narrow enough for an exact reference calculation.
2. Implement `evals/analyst/generator.py` to create deterministic tables and structured task cases from scenario parameters. Store disclosed development cases in `evals/analyst/scenarios.yaml`. Generate variable row order, group count, values, filters, empty results, and invalid rows. Fix each case's seed and input hash when it is materialized.
3. Implement `evals/analyst/oracle.py` as the protected calculation of expected answers. Check it against hand-worked examples in `tests/test_scenarios.py`. The candidate harness may use the same input data, but it cannot import or see the oracle or reference outputs.
4. Implement the initial case runner in `src/self_heal/evaluation.py`. It launches a fixed harness version with a controlled task/input, collects the structured answer, compares it with the oracle, and measures externally enforced step/tool/time budgets. Record individual trials instead of only a pass flag.
5. Establish three disclosed baseline cases: a small success, an edge case, and a larger supported task that the initial harness fails for a known correctness or budget reason. Freeze the failing case before asking a model for a patch.

## Configuration

Use the fixed agent model from Phase 1 for live comparisons. Fixture seeds, evaluator limits, and expected answers belong in protected configuration or evaluator storage, not in the editable `harness/` directory. Set the Docker runner image name in `.env`; candidate execution with this boundary is wired in Phase 4.

## Completion checks

- Hand-checked oracle examples pass; repeated generation from the same parameters yields identical inputs and answers.
- The initial harness passes the small case and reliably fails the bulk case under the declared limits. The evaluator reports the violated requirement, not just whether an exception occurred.
- A deliberately wrong answer, budget increase, or missing output is rejected by the evaluator. Old successful cases remain part of the regression bank.

**Phase deliverables:** `evals/analyst/{generator,oracle,scenarios.yaml}`, `src/self_heal/evaluation.py`, `tests/{test_scenarios,test_evaluation}.py`, and the evaluation fields of `config/analyst.yaml`.
