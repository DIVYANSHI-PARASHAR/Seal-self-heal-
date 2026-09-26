# Phase 1 — Base analyst and controlled data

**Outcome:** a small custom agent can answer a simple structured table question using a model and two or three explicit tools. Its inputs and outputs are reproducible enough for later evaluation.

## Build

1. Implement the Python package and CLI entry point in `pyproject.toml` and `src/self_heal/cli.py`. Add the smallest dependencies needed for the OpenAI-compatible model API, LangSmith SDK, configuration, PyMongo, and pytest; pin them in the lockfile. The first CLI command runs one analyst task and prints the answer plus run ID.
2. Implement `src/self_heal/model.py` as a thin OpenAI-compatible OpenRouter client for the agent and evolution calls. Keep the client interface suitable for LangSmith `wrap_openai` in Phase 3; do not add a LangChain agent framework. Keep agent model/settings stable across baseline and candidate runs. Supply a scripted model double for local component checks; a live provider call is a separate connection check.
3. Implement `harness/agent.py` as a bounded model → tool → result loop with a clear stop condition and structured final answer. Implement `harness/tools.py` with schema inspection and bounded row reading; `harness/context.py` assembles instructions and recent tool results. This is the editable harness, not a prebuilt alternate analyst mode.
4. Add controlled inventory tables with fields such as `sku`, `warehouse`, `category`, `on_hand`, and `reserved`. Keep the initial working question small enough for row-by-row reading. Define a larger grouping question that stresses the initial approach under the same fixed call/context budget. The data generator and expected answers are completed in Phase 2.
5. Fill `config/analyst.yaml` with the supported task and output schema, allowed fields, tool-call/step/token/time limits, and the `harness/` edit boundary. Define missing-value and invalid-row behavior explicitly; do not silently invent numeric values.

## Configuration

Copy `.env.example` to `.env`. Supply `OPENROUTER_API_KEY` and `OPENROUTER_AGENT_MODEL` for a live smoke run. `OPENROUTER_EVOLUTION_MODEL` becomes necessary in Phase 4. The agent process must not read the Atlas URI or GitHub credentials.

## Completion checks

- A small fixture task produces the correct structured answer, both with a scripted model response and in a live smoke run.
- The tool loop exposes only registered tools, obeys the configured step limit, and reports a clear failure when it cannot complete.
- Source and data are independent of any future generated improvement. There is no prewritten aggregation tool to select.

**Phase deliverables:** `pyproject.toml`, `harness/{agent,tools,context}.py`, `config/analyst.yaml`, `src/self_heal/{cli,model,settings}.py`, and a first small inventory fixture under `evals/analyst/`.
