# Automatic evolution from a failed question

## Goal

When an operator question produces a verified capability gap or harness bug, start an evolution job automatically. Show its real evidence and progress on an Evolve page. If a candidate passes the protected selection gates and its exact commit is activated, run the original question again on that version and show the new run. If it cannot be fixed safely, keep the incident and reason visible without presenting a successful repair.

The question stays in the top bar on the Evolve, Runs, Evaluations, Versions, and final answer pages. The original run, evolution job, candidate, evaluation plan, activated version, and rerun have stable links to one another.

## Current state and missing pieces

- `POST /api/runs` executes and returns one run. The browser always opens `#run-details`; it never queues evolution. The existing gap panel only displays candidates that were started elsewhere.
- `EvolutionController.evolve(run_id)` already handles inventory reproduction, generated cases, screened harness patches, baseline-versus-candidate trials, and conditional promotion. It is invoked from the CLI, not the web server. Its work is synchronous and has no progress event stream.
- The reviewed logistics threshold tool is built into `harness/logistics.py`, and the web path invokes it directly. The four logistics checks in `logistics_evaluation.py` evaluate that reviewed implementation; they are not candidate selection or promotion. The web path explicitly rejects an active logistics candidate because `CandidateRunner` and its Docker bridge are inventory-only.
- The threshold question already succeeds on the current logistics v2 path, so it cannot honestly produce a new gap on that version. A demonstration of the full cycle must start with an explicitly pinned logistics v1 baseline or use a genuinely new, unsupported capability. Do not silently downgrade the user's active version or relabel the existing reviewed v2 change as automatic evolution.
- A model proposal is currently one JSON completion containing a hypothesis and diff; it does not execute tools. The UI can show actual analyst tool invocations from run evidence and candidate trials, and can show the proposal model call as a separate step. It should never invent model tool calls.

## Implementation sequence

### 1. Detect an eligible incident and create one durable job

Add a trusted incident classifier after the run record is complete. Auto-start only for `unsupported` with `limitation_kind=capability_gap`, a deterministic harness error with a supported contract, or an independently verified wrong answer. Network, Atlas, model-provider, and trace outages are operational failures, not patch requests. An answered run with no oracle check is not automatically called a bug.

Persist an `evolution_jobs` record in Atlas keyed by the incident run ID (unique index) before returning the run response. Save the original question, input kind, dataset ID and content hash, task family, observed commit, current stage, timestamps, and links to cases/candidates/selection. Use a conditional claim or lease so double clicks, retries, concurrent requests, and server restarts cannot start duplicate jobs. Return `evolution_job_id` and `evolution_url` with the original run.

### 2. Run evolution outside the HTTP request

Move controller invocation into a supervised background worker. The request returns as soon as the incident and job are recorded. The worker resumes or marks interrupted jobs on startup; it does not depend on a browser tab remaining open. Add bounded retries only for transient infrastructure failures, respecting existing patch-attempt limits. Record terminal states such as `activated`, `rejected`, `needs_contract`, `blocked`, and `operational_error` with concrete reasons.

Emit persisted stage events from the real controller boundaries: incident classified, trace read, original case frozen, generated case frozen, baseline reproduced, proposal received, diff screened, candidate commit created, evaluation plan frozen, each baseline/candidate trial completed, selection decided, and promotion completed. Store IDs, timings, commits, and redacted evidence references, not raw private rows, oracle answers, credentials, or private case content. The UI consumes these records through `GET /api/evolution-jobs/{id}` and `GET /api/evolution-jobs/{id}/events`; polling is enough initially, with SSE optional later.

### 3. Make logistics a real candidate path

Extend the candidate runner and container RPC to accept a typed logistics bundle. Expose only the approved `inspect_catalog`, `inspect_relation`, and bounded `read_shipments` operations; preserve dataset scoping, frozen time semantics, cursor validation, page/byte/time budgets, and no Atlas credentials in the container. Dispatch the candidate's logistics agent/tool registration from its pinned `harness/` commit, rather than always importing the server's built-in `LogisticsAgent`.

Add logistics-specific scenario generation, a frozen original case, an independent oracle, generated reproduction, private variations, negative refusals, and inventory regressions to the controller/evaluator. The comparison must run the same frozen cases and limits against the old commit and proposed commit. A proposed `count_customers_over_shipment_threshold` tool must be a screened harness-only diff and a tested candidate commit. A passing standalone logistics tool check is insufficient for promotion.

### 4. Select and activate the exact tested code

Keep the existing patch scope, Docker isolation, immutable evaluation plan, repeat trials, resource ceilings, trace requirements, and `PromotionManager` compare-and-swap. Compute a transparent scorecard from stored trial records: original incident, newly generated case, existing regressions, private validations, negative refusals, resource/cost checks, and overall decision. Show baseline and candidate side by side for each case, with failures and skipped trials visible. Do not reduce selection to a single percentage that hides required gates.

The active-version record changes only after all required gates pass for the exact candidate commit and environment identity. In-flight runs stay pinned to their starting version. If the parent version changes during evaluation, mark the candidate stale and reevaluate; do not overwrite the active version. Keep the previous version available for rollback.

### 5. Add the Evolve page and automatic navigation

Add `#evolve/{job_id}` and an Evolve item in the sidebar. On an eligible run response, navigate there immediately and keep the original question in the shared top bar. On reload, use the job ID in the URL to restore progress. The page should show:

1. Original outcome, version, Atlas record, LangSmith trace, and the exact ordered analyst tool calls (including `0 calls` where true).
2. What the evaluator identified as fixable, the frozen original/new case IDs, and the baseline reproduction result.
3. Proposal hypothesis, proposed tool name, screened diff, changed files, candidate commit, and code-change status. The code panel reflects the saved diff; it never animates a fictional edit.
4. A live baseline-versus-candidate evaluation matrix with case role, run IDs, answer/outcome, measured tools/pages/tokens/time, pass/fail reason, and trace links. Protected validation details remain redacted.
5. Activation result, active/previous commit, and a linked rerun. Rejected or blocked jobs remain on this page with the actual failure reason and no auto-rerun claim.

Keep the question input visible on every page, as in the supplied reference UI. Distinguish original run tool calls, proposed tool definition, evaluation tool calls, and final rerun tool calls with explicit labels.

### 6. Rerun after activation and return to Ask

When the job reaches `activated`, the server starts exactly one rerun using the original question, original immutable dataset, and newly active commit. Record `rerun_run_id` and link it to the incident/job. If that run answers successfully, the UI navigates to `#ask` with the completed answer and evidence visible, including the new tool call. If it fails, keep the Evolve page open with the failed rerun and avoid a success banner. The rerun trigger is idempotent and survives refresh or reconnect.

## Proposed API and record changes

- `POST /api/runs`: unchanged question input; response gains `evolution_job_id`, `evolution_url`, and `evolution_state` only when an incident was queued.
- `GET /api/evolution-jobs/{id}`: summary, question, stage, linked run/candidate/plan/version/rerun IDs, scorecard, and safe display data.
- `GET /api/evolution-jobs/{id}/events`: ordered persisted progress with cursor-based polling.
- `GET /api/runs/{id}`: include linked evolution job and, for the final run, its originating incident.
- Atlas: `evolution_jobs` with unique incident ID, stage/event sequence, lease ownership/expiry, bounded attempts, and rerun ID. Reuse existing runs, capability gaps, eval cases, evaluations, candidates, selection plans, and versions as the detailed source of truth.

## Verification and demo acceptance

1. Submit an eligible baseline logistics v1 threshold question. It records a real capability gap, zero shipment tool calls, and automatically opens Evolve.
2. The job creates an immutable case for that question and a new related case, reproduces the baseline failure, proposes and commits the bounded tool change, then records every selection trial against both commits.
3. The Evolve page shows actual model/proposal steps, exact tool calls and arguments where available, the diff, four or more logistics variations, inventory regressions, per-case comparison, and the promotion decision. Protected rows and answers do not leak through the UI.
4. A passing exact commit becomes active. One automatic rerun of the original question uses that commit, answers correctly, shows its actual new tool call and trace, and returns the user to Ask with the answer displayed.
5. A failing candidate, out-of-contract request, duplicate request, stale parent, infrastructure outage, refresh, and server restart never cause duplicate promotion or a false success screen. Existing inventory runs and CLI evolution continue to work.

Implement in this order: durable job/trigger; instrumented inventory worker and Evolve page; logistics candidate bridge and protected evaluator; promotion/rerun integration; full browser and restart tests. This keeps each step independently testable and avoids using the reviewed built-in logistics tool as evidence of a generated repair.
