# Phase 4 — Eval creation and harness evolution

**Outcome:** an observed task limitation produces a validated, frozen eval and a real model-generated candidate change to the editable harness.

## Build

1. Implement `src/self_heal/controller.py` to detect a task that missed its correctness or resource requirement, load its LangSmith trace via the ID stored in Atlas and pin the baseline commit, and start one bounded improvement attempt. Exceptions also enter through this path. Refuse a behavioral patch when evidence or expected task behavior is unknown; record a diagnostic-only result if logging is the justified change.
2. Use `prompts/scenario.md` to ask the evolution model for a structured scenario within the Phase 2 task contract. Have the protected generator validate and materialize its table as an immutable Atlas dataset, then have the oracle freeze the expected result separately. Replay the baseline on the observed dataset and again on the newly generated one; require both relevant failures to reproduce before patch generation. Generate separate private Atlas datasets for candidate validation. Store each case's dataset ID/hash, origin, contract/oracle version, and development exposure in protected Atlas history.
3. Use `prompts/diagnose.md` and `prompts/evolve.md` to send the model relevant redacted LangSmith trace spans, supported contract, editable harness source, the verified reproduction, and relevant accepted/rejected attempts from Atlas. Request one stated hypothesis and one coherent reusable source change. The model must generate the new capability; the application must not choose a prepared large-dataset mode or a canned patch.
4. Implement `src/self_heal/repository.py` to create a worktree from the exact baseline, apply the proposed diff, and pin a candidate commit. Reject edits outside `harness/`, path/symlink escapes, changed limits, and obvious fixture answers or dataset identifiers before evaluation. Keep the original checkout intact.
5. Implement `src/self_heal/runner.py` and the one local Docker image in `Dockerfile` for generated-code execution. Give the candidate its source, task, and a run-scoped table-access interface for only its assigned Atlas dataset; do not mount table snapshots, the oracle, private evals, GitHub/Atlas credentials, or the full host repository. The trusted side resolves bounded page requests against Atlas and rejects dataset switching, arbitrary MongoDB operations, and limit violations. A candidate-generated aggregation tool can iterate allowed pages inside one model tool call and compute its own result, without a prewritten aggregation endpoint. Route model and tool-call envelopes through the fixed supervisor interface so the trusted process can create LangSmith spans without giving the candidate a LangSmith key. Enforce time/resource and data-read limits independently of those spans. Keep the bridge minimal and test that candidate failures remain traceable. A worktree is source isolation, not an execution sandbox.

## Configuration

Fill `OPENROUTER_EVOLUTION_MODEL` in `.env`. Build the configured Docker image once and start Docker before attempting generated-code evaluation. Keep the same `OPENROUTER_AGENT_MODEL` for old and new harness runs. Attempt limits and editable paths come from protected `config/analyst.yaml`, not candidate code.

## Completion checks

- The observed bulk limitation becomes a frozen case and the baseline fails it under the declared requirement.
- The proposal includes a readable hypothesis and a diff that adds a reusable tool or context mechanism, with no task answer embedded. It is committed in a separate worktree.
- Out-of-scope edits, absent ground truth, unreproduced failures, and attempts beyond the limit are rejected with recorded reasons. Candidate code cannot read protected oracle files, other Atlas datasets, or Atlas credentials in the runner.

**Phase deliverables:** `src/self_heal/{controller,evolution,repository,runner}.py`, `prompts/{scenario,diagnose,evolve}.md`, `Dockerfile`, `tests/{test_edit_scope,test_evolution_cycle}.py`.
