# Phase 6 — Untouched assessment and end-to-end demonstration

**Outcome:** the selected harness faces a task that did not help select or tune it, and the full improvement history is easy to inspect.

## Build

1. Reserve a small final-assessment protocol before evolution: supported but unseen scenario parameters, new immutable Atlas datasets with frozen IDs/hashes, an independent oracle, and the same model/settings and budgets used for comparison. Keep final dataset IDs, case metadata, and expected answers inaccessible to the proposer and candidate; bind each run's table interface only to its assigned dataset and exclude final cases from candidate-selection queries.
2. Freeze the selected harness commit after Phase 5. Run the final task or small final batch once under the reserved protocol. Report every outcome and resource measure separately from the selection score. If a failure later informs another patch, mark the case as consumed and draw new untouched cases for any subsequent final claim; retain the attempt history.
3. Run one complete cycle from an initial successful small task through the bulk limitation, newly validated eval, baseline replay, generated diff, candidate selection, Atlas activation, and a new task using the accepted version. Show the tool list/context behavior before and after so the architectural change is visible.
4. Add a compact CLI view of the Atlas improvement history that links the incident, LangSmith traces, eval case, hypothesis, exact source diff/commit, baseline-versus-candidate trials, acceptance or rejection, active version, and separate final result. The primary proof is the working harness and evidence, not a dashboard.
5. Verify the repository docs and setup instructions against the real commands, inputs, environment variables, and recorded results. Remove scaffold comments only where implementation exists. Do not claim transfer beyond the supported analyst task family or a certainty the small final sample cannot establish.

## Configuration

The same `.env` values configured in earlier phases are sufficient. Final table rows live as protected Atlas datasets; their seeds, IDs, and answers remain in protected evaluator storage outside the editable checkout and candidate container. The trusted runner supplies only scoped row access during an authorized final trial. No new hosting or GitHub integration is required to demonstrate the local cycle.

## Completion checks

- The exact accepted version succeeds or fails on untouched cases, and the outcome is reported honestly with individual trials and measured cost.
- Another task over a different Atlas-backed dataset uses the generated capability without another patch cycle; previously successful small tasks still work.
- From Atlas records and linked LangSmith traces, a reviewer can inspect the limitation, newly created eval, source change, tests, decision, and fresh run without relying on a presentation.

**Phase deliverables:** integration checks in `tests/`, the relevant CLI view, final-assessment controls in `evals/analyst/`, and updated `README.md`/docs reflecting observed behavior.
