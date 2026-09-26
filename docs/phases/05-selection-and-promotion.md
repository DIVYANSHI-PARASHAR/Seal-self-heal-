# Phase 5 — Candidate selection and activation

**Outcome:** only a candidate that improves the task within fixed limits and preserves prior behavior becomes the version used for fresh work.

## Build

1. Extend `src/self_heal/evaluation.py` to evaluate the original incident case, every existing regression, and several fresh private validation cases. Generate and materialize new immutable Atlas datasets independently of the proposed patch, with different row order, group counts, fields, filters, values, empty groups, and invalid rows. Freeze their dataset IDs/hashes, the candidate's exact commit, and the evaluation plan before running it.
2. Run baseline and candidate against the same immutable Atlas dataset ID/hash for each case, with the same scoped table interface and a fresh read cursor/counters for every trial. Reject a comparison if the dataset changes. Keep the agent model, settings, dependency environment, and budgets constant. Measure correctness, tool calls, table pages/bytes, and elapsed time outside editable harness code. Retain all individual results in Atlas with their LangSmith trace IDs, including failed attempts and repeated live model trials where needed. Use LangSmith for detailed inspection; the protected evaluator supplies authoritative scores and limits.
3. Implement acceptance gates for reproduced baseline failure, original-case success, no regression, validation success, fixed budgets, complete evidence, in-scope patch, and acceptable cost change. A candidate cannot pass by returning a hardcoded answer, disabling a tool, raising a limit, or hiding an error. Clearly label uncertain/flaky outcomes rather than selecting on one lucky run.
4. Implement `src/self_heal/promotion.py` to match the decision to the exact tested commit and environment identity. Conditionally update Atlas's active-version record only if its parent still matches. Re-evaluate after a parent change. Start a fresh task from the accepted commit; keep in-flight runs pinned and previous versions available for rollback.
5. When a candidate fails, retain its hypothesis, diff, score, cost, and reason in Atlas. A validation case whose feedback guides another patch is development evidence; record that exposure. Do not delete cases or change the oracle to improve a candidate's apparent score.

## Configuration

Keep acceptance thresholds, retry counts, table-read limits, and resource limits in protected `config/analyst.yaml`; record their hash with each evaluation. No candidate-specific env value may change the scoring contract. Atlas access stays with the trusted runner and supervisor, and Docker stays the execution boundary for generated candidates.

## Completion checks

- The old commit fails the original requirement; the selected commit passes the original, regression, and fresh validation cases within unchanged limits.
- A deliberately hardcoded patch, regression, stale-parent activation, changed dataset hash, and changed evaluation identity are each rejected.
- Atlas points to the exact tested commit. A new task uses it, rollback can select the prior version, and every accepted or rejected attempt remains inspectable.

**Phase deliverables:** `src/self_heal/{evaluation,promotion,controller,storage}.py`, `tests/{test_evaluation,test_promotion,test_evolution_cycle}.py`, and protected acceptance settings.
