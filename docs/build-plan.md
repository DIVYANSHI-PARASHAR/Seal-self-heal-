# Implementation phases

Self-Heal's first build is one custom Python analyst harness plus an in-repo supervisor. An observed task limitation becomes a validated eval; the supervisor generates a reusable harness change; protected checks decide whether the exact candidate commit becomes active. [Architecture](architecture.md) describes the boundaries, and [evaluation design](evaluation.md) defines the case roles and evidence rules.

The phases are sequential because each phase provides evidence or a protected boundary needed by the next. Phase 1 stores analyst tables in Atlas, reads them through a trusted, run-scoped interface, and returns an explicit `unsupported` outcome when a natural-language request exceeds current capabilities. Phase 3 makes those outcomes searchable in LangSmith and Atlas before autonomous changes begin. Phase 4 turns validated capability gaps into evals and proposed harness changes; Phase 5 evaluates them, and Phase 6 tests the selected harness on untouched tasks.

| Phase | Outcome | Plan |
| --- | --- | --- |
| 1. Base analyst and Atlas data | A small working agent, Atlas-backed table data, scoped reads, fixed model interface | [01-base-analyst.md](phases/01-base-analyst.md) |
| 2. Protected eval foundation | A trustworthy oracle, deterministic Atlas datasets, baseline cases, fixed budgets | [02-eval-foundation.md](phases/02-eval-foundation.md) |
| 3. LangSmith tracing and Atlas history | Model/tool traces in LangSmith; searchable unsupported/capability-gap tags and durable records linked to Atlas datasets | [03-tracing-and-atlas.md](phases/03-tracing-and-atlas.md) |
| 4. Eval creation and evolution | Wrong answers and explicit capability gaps become frozen cases when independently gradable; the model generates a bounded harness patch | [04-eval-creation-and-evolution.md](phases/04-eval-creation-and-evolution.md) |
| 5. Candidate evaluation and activation | Independent regression/transfer checks, exact-commit promotion, rollback | [05-selection-and-promotion.md](phases/05-selection-and-promotion.md) |
| 6. Untouched assessment and demo | Fresh-task evidence and an end-to-end, inspectable account of the cycle | [06-final-assessment.md](phases/06-final-assessment.md) |

## Setup to complete when services are available

For a fresh repository, use [SETUP.md](../SETUP.md) for boilerplate and service access before Phase 1. It does not add or replace an implementation phase.

Copy [`.env.example`](../.env.example) to `.env` and fill in the Atlas sandbox URI and OpenRouter key/model IDs before Phase 1; LangSmith key/project are needed in Phase 3. `.env` is ignored by Git. Install the project dependencies through `uv`, verify Atlas table seeding and one live model/tool run in Phase 1, and start Docker before candidate execution. Phase 3 must produce a retrievable LangSmith trace linked to the Atlas run and dataset. The participant resource guide provides an Atlas sandbox invite, OpenRouter credits for checked-in participants, and $50 in LangSmith credits plus Deployments access. Redeem the LangSmith offer through its form within 10 days of the event; the guide says to add a card to display the credits. This plan uses tracing only, so LangSmith Deployments, LangGraph, and extra MongoDB search/embedding services are not setup requirements.

The local evolution loop uses Git worktrees and commits. GitHub credentials are unnecessary for generating or evaluating a patch. Publishing a branch or PR can be added after the local loop works, using the same tested commit and recorded evidence; it is not part of the promotion gate.

## End state

One small task succeeds over an Atlas-backed table under the initial harness. A bulk task over a larger Atlas dataset fails a fixed correctness or resource requirement. An unsupported natural-language request also produces a conversational refusal plus a queryable capability-gap record and trace. The system turns independently gradable observations into frozen evals and confirms baseline failures. Its model-generated patch adds a reusable capability and supporting context policy; the original case, existing regressions, and fresh validation cases pass within unchanged limits. Atlas holds the immutable table rows and records every run, proposal, rejection, and activation with dataset hashes and trace IDs; LangSmith holds the detailed model/tool traces. A new task runs from the accepted commit, and a final untouched assessment reports what transferred without tuning the selected harness.

**Implementation status:** Phase 1 is complete: the base analyst seeded and read an Atlas-backed table, passed a live OpenRouter tool-call task, and returns `outcome=unsupported` with a conversational refusal for unsupported questions. Phases 2–6, persisted capability-gap traces and history, and the Docker-backed improvement cycle remain to be implemented.
