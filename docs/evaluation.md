# Evaluation design

Self-Heal turns observed limitations into persistent eval cases, then accepts harness changes only when independent checks support them. The first domain is structured table analysis with a fixed contract for filters, grouping, and numeric aggregates.

**Preparation status:** this document defines the intended evaluation design. The generator, oracle, runner, acceptance gates, and live comparisons are not implemented in this repository yet.

## Creating an eval from an observation

The supervisor records the task, input/environment references, LangSmith trace ID, source/model/configuration identities, observed result, and violated requirement in Atlas. It reads model/tool calls and errors from LangSmith when diagnosing the incident. The trigger can be a wrong result, missing capability, resource exhaustion, or exception.

The model proposes a structured scenario within the supported contract. `evals/analyst/generator.py` validates that proposal and materializes the inputs. `evals/analyst/oracle.py` computes the correct result independently of the candidate. Freeze the case before patch generation and replay the baseline on both the observed task and the generated case. The new case must also fail the old harness; separate fresh variations stay hidden for candidate validation.

An exception does not supply the correct answer. An unsupported scenario or one without trustworthy ground truth cannot authorize a behavioral change. The supervisor may record it for investigation or propose diagnostic improvements, but must not invent an expected answer just to complete the cycle.

A scenario record should identify:

- Task family, user-visible task, structured query/requirements, and incident provenance.
- Input fixture reference, generation parameters, seed reference, and input hash.
- Contract/oracle version and the protected expected-result reference.
- Correctness invariants and externally enforced resource limits.
- Case identity, declared evaluation role, creation time, and exposure history.

The model may propose tasks and variations; it cannot edit the generator, reference calculation, grading rules, or budgets. Private seeds and answers remain outside its accessible workspace and database view.

## Evaluation roles

| Role | Purpose | Exposure and lifecycle |
| --- | --- | --- |
| Original reproduction | Verify the observed limitation and its resolution | Disclosed to the proposer after validation; retained permanently as a regression |
| Existing regressions | Preserve known capabilities and previously fixed cases | Development evidence; never silently delete a failure to improve the score |
| Fresh validation | Check transfer while deciding whether to accept a candidate | Generated independently of the proposed patch, private initially; feedback used in selection is development evidence |
| Final assessment | Assess the selected, frozen harness on untouched tasks | Excluded from candidate selection and tuning; report all outcomes after selection |

Fresh validation is not a pristine final test merely because the proposer has not seen its inputs. Repeated pass/fail feedback influences selection. Limit patch attempts, retain all results, and record when a case becomes exposed.

If final-assessment feedback guides further development, that case becomes development evidence. A later final assessment requires new untouched cases and disclosure of the prior attempts. A failed final assessment cannot be erased or renamed into a successful demonstration.

## Comparing baseline and candidate

Run the old and new harness against identical case inputs, reset tool/data state, and record the same model/settings and execution environment. The baseline must fail the original requirement; the candidate must satisfy it. Neither is allowed to alter task truth or increase the acceptance budget.

Grade outside candidate execution. LangSmith traces explain behavior and supply reported model usage; the protected grader and runner remain authoritative for correctness, tool-call count, elapsed time, and budget decisions. Provide only the task and allowed dataset to that process; do not mount the oracle, expected answers, private controls, or entire repository. A candidate cannot self-report the authoritative pass/fail result or resource count.

Measure:

- Exact task correctness under the declared output contract, including omissions, duplicates, and invalid outputs where relevant.
- Model/tool calls, externally observed token usage, elapsed time, and budget violations.
- Individual trial results for the original case, existing regressions, and fresh validation.
- Source/configuration/environment identities, LangSmith trace ID, and the mechanism changed by the patch.

A lower token count does not compensate for a wrong answer. Additional work is permitted only within the fixed, declared acceptance limits. The comparison must not silently change models or give the candidate extra retries.

Deterministic fixtures and a deterministic oracle stabilize grading; they do not make an LLM's choices deterministic. Use scripted model responses for component checks and a few repeated live trials for critical end-to-end behavior. Preserve every trial and report observed variation rather than claiming statistical certainty from a small sample.

## Analyst variations

For a candidate that adds aggregation and changes context selection, use several supported variations:

- Reorder rows and rename entities so answers cannot depend on input order or known names.
- Change table size, group counts, and the supported grouping or filter field.
- Include empty results, zero totals, offsetting entries, and missing values with contract-defined semantics.
- Keep small-table questions that already worked before the change.

Reference answers come from the protected calculation, not the generated aggregation tool. Validate the oracle itself against hand-checked examples before relying on it. The generator varies data and requirements; it does not produce a replacement authoritative grader for each proposed patch.

A fresh question over a new dataset tests reuse within this family. It does not establish cross-domain generalization.

## Acceptance and reporting

The selection gate requires a reproduced original failure, a screened in-scope diff, a passing original case and regression suite, passing fresh validation under fixed budgets, sufficient execution evidence, and matching candidate/evaluation identities. Where repeated trials are required, their acceptance rule is fixed before candidate testing.

Keep proposed changes attributable: one coherent mechanism may include a tool and the context guidance needed to use it. Check for embedded answers, fixture-specific values, unauthorized files, and weakened limits before full evaluation. A leakage screen is useful evidence, not a proof that overfitting is impossible.

Record rejections with their hypotheses, diffs, scores, costs, and reasons. Later proposals should consult that history. Reevaluate any proposed removal of an existing mechanism rather than silently pruning it.

After selection, pin the chosen version and run the final assessment once according to the reserved protocol. Store and present its results separately from the acceptance score. A diagnostic improvement, accepted candidate, successful fresh execution, and successful final assessment are distinct outcomes.

## Research alignment

[RRSI](https://arxiv.org/html/2609.24972v2) motivates controlling how finite feedback drives persistent harness edits. Our small implementation borrows evidence history, attributable changes, leakage checks, and attention to noise/cost. Automatically producing validated eval cases from operational observations is our proposed workflow, rather than a claim that the paper implements it.
