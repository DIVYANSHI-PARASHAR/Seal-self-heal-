# Phase 3 — LangSmith tracing and MongoDB Atlas history

**Outcome:** every task run has a detailed LangSmith trace and a linked Atlas record; prior attempts remain queryable for later proposals.

## Build

1. Implement `src/self_heal/contracts.py` for stable task/run/case/candidate/trial/version IDs and linked records. Include the source commit, config hash, model ID/settings, fixture ID, timestamps, case exposure role, and LangSmith root trace ID where applicable. Do not define or persist a second per-event trace schema.
2. Implement `src/self_heal/telemetry.py` as a thin LangSmith SDK adapter around the fixed model/tool interface. Use `wrap_openai` for the OpenRouter-compatible model client and LangSmith spans for the task and tool boundary. Attach the shared run ID and version metadata. Trace requests, responses, tool arguments/results, errors, duration, and reported usage; apply redaction before upload. Keep the SDK key in the trusted supervisor, not in generated candidate code.
3. Implement `src/self_heal/storage.py` with PyMongo against the Atlas sandbox cluster. Store compact `runs`, `eval_cases`, `candidates`, `evaluations`, and `versions` records, including the trace ID and independently measured outcome/resource summary. Index run ID, case ID, candidate commit, task family, and active-version identity. Do not create an `events` collection or copy full model/tool payloads into Atlas.
4. Preserve each state transition, rejected hypothesis, and measured outcome. Add retrieval by task family and changed mechanism so Phase 4 can consult prior attempts. Record case exposure as history instead of overwriting a private label.
5. Add connection checks: one traced live model/tool run must appear in LangSmith, and its Atlas run record must resolve to the same trace ID. Use the LangSmith UI for detailed inspection and SDK retrieval by ID for diagnosis; the project CLI only needs a compact run summary and trace link/ID. Mark upload or retrieval failures as incomplete evidence. Define redaction/retention expectations without building a custom trace viewer or ingestion pipeline.

## Configuration

Fill `ATLAS_URI` and `ATLAS_DATABASE` using the provided Atlas sandbox cluster. Create a database user with only the required access and allow this machine's network address. Set `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, and `LANGSMITH_TRACING=true` in `.env`; add `LANGSMITH_WORKSPACE_ID` only if the API key belongs to multiple workspaces. The supervisor holds both service credentials. The candidate runner receives neither key.

The participant guide offers $50 in LangSmith credits and Deployments access; redeem the offer via its form within 10 days of the event. It says a card must be added for the credits to appear. This phase needs LangSmith tracing only. LangChain/LangGraph agent frameworks, LangSmith Deployments, a separate telemetry database, and a custom trace UI are outside the first build.

The [LangSmith guide for OpenAI-compatible providers](https://docs.langchain.com/langsmith/trace-with-openai-compatible) covers `wrap_openai`; the [OpenAI tracing guide](https://docs.langchain.com/langsmith/trace-openai) shows task/tool spans and required environment variables. Use the SDK to retrieve run data for diagnosis rather than maintaining a duplicate log store.

## Completion checks

- A small and a failing bulk run each have a LangSmith task trace showing model/tool activity and errors, linked by ID to an Atlas run with the exact harness version and independent outcome.
- The supervisor can retrieve a trace by its Atlas reference; missing or redacted evidence is explicit. Secrets and protected answers do not appear in the trace, and a worker restart does not erase Atlas attempts.
- A synthetic rejected attempt can be retrieved from Atlas by task family and linked to its LangSmith trace for the next proposal.

**Phase deliverables:** `src/self_heal/{contracts,telemetry,storage,settings,cli}.py`, `tests/test_telemetry.py`, and the Atlas/LangSmith fields in `.env.example`.
