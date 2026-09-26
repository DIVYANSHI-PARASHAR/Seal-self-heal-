# Fresh-repository setup (before Phase 1)

Use this guide to prepare a **new, empty Self-Heal repository**. It covers repository boilerplate, accounts, and configuration only. The six implementation phases in [docs/build-plan.md](docs/build-plan.md) remain the build order and acceptance criteria. Do not copy the current repository's implemented harness, supervisor, tests, fixtures, Dockerfile, or lockfile into the new repo.

If this is an event submission, create the new repository and its implementation during the permitted build window. Keep any earlier planning material identifiable as preparation. The README template below describes the project, without claiming that unfinished features already work.

## 1. Create the repository and directories

Create the repository under `/Users/ishwantsingh/Projects/`, using a **new directory name** so the existing `self-heal` checkout remains intact. Initialize Git and, if you want a remote, create a GitHub repository and set it as `origin`. GitHub is for source publication; the local improvement loop uses Git commits and worktrees and needs no GitHub API token.

Start with this layout. The `.gitkeep` files only preserve empty directories in Git; remove each one when the phase adds real files there.

```text
README.md
SETUP.md                    # This guide, if retained in the new repo
.env.example
.gitignore
docs/
  build-plan.md             # Index of the same six phases
  phases/
    01-base-analyst.md
    02-eval-foundation.md
    03-tracing-and-atlas.md
    04-eval-creation-and-evolution.md
    05-selection-and-promotion.md
    06-final-assessment.md
config/.gitkeep
evals/analyst/data/.gitkeep
harness/.gitkeep
prompts/.gitkeep
src/self_heal/.gitkeep
tests/.gitkeep
```

Write or carry over **planning documents only** under `docs/`, clearly marked as preparation if they predate implementation. Keep the six phase names and ordering. The phase files govern when code and tests are created:

| Phase | Files that begin here |
| --- | --- |
| 1. Base analyst and Atlas data | `pyproject.toml`, `harness/{agent,tools,context}.py`, `config/analyst.yaml`, `src/self_heal/{cli,model,settings,table_store}.py`, first Atlas-backed table |
| 2. Protected eval foundation | `evals/analyst/{generator,oracle,scenarios.yaml}`, deterministic Atlas datasets, protected checks in `tests/` |
| 3. LangSmith tracing and Atlas history | `src/self_heal/{contracts,telemetry,storage}.py`, trace/storage checks |
| 4. Eval creation and evolution | `src/self_heal/{controller,evolution,repository,runner}.py`, `prompts/{scenario,diagnose,evolve}.md`, `Dockerfile` |
| 5. Candidate selection and activation | `src/self_heal/{evaluation,promotion}.py`, acceptance and rollback checks |
| 6. Untouched assessment and demo | final sealed evaluation cases, reports, and demo instructions |

Phase 1 creates and locks dependencies; Phase 4 builds the candidate image. Creating empty directories now does not count as implementing any phase.

## 2. Add a truthful README

Use this as the initial `README.md`. Update its status and usage instructions as each phase lands. Keep the README about the project itself.

```markdown
# Self-Heal

Self-Heal is a task-adaptive agent harness. A trusted supervisor turns observed task limitations into reproducible evaluations, proposes a reusable harness change, tests it against existing and fresh cases, and activates only a validated version.

The first use case is a small Python analyst for structured tables. The editable harness owns its tools and context policy. The protected supervisor owns the oracle, evaluation limits, trace integration, and version decisions.

MongoDB Atlas will hold structured analyst tables and compact run, case, candidate, evaluation, and version records. A trusted table interface will scope each run to its assigned dataset. LangSmith will hold detailed model and tool traces linked to those records. OpenRouter will supply model calls. Candidate code will run in a local Docker container without Atlas credentials; Git will pin each evaluated version.

**Status:** repository scaffold and service configuration only. Harness behavior, evaluations, tracing, storage, and the improvement loop are built in the six phases described in [docs/build-plan.md](docs/build-plan.md).

See [SETUP.md](SETUP.md) for account and environment setup.
```

For `docs/build-plan.md`, keep the existing six-phase sequence and links to its six phase files. Do not insert a new implementation phase called “setup”; this guide is a prerequisite checklist.

## 3. Ignore local state and secrets

Create `.gitignore` with at least:

```gitignore
.env
.env.*
!.env.example
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
.DS_Store
.self-heal/
*.egg-info/
```

The `.env.example` file is safe to commit because its secrets remain blank. Never commit `.env`, a filled connection string, API keys, traces containing sensitive inputs, or local candidate worktrees.

## 4. Add the environment template

Create `.env.example` with the same names used by the current implementation:

```dotenv
# Copy this file to .env and fill the blank values. Never commit .env.
# The trusted runner and supervisor use this Atlas connection.
ATLAS_URI=
ATLAS_DATABASE=self_heal

# Use OpenRouter model IDs available to your account.
# Keep the agent model/settings fixed for baseline and candidate comparisons.
OPENROUTER_API_KEY=
OPENROUTER_AGENT_MODEL=
OPENROUTER_EVOLUTION_MODEL=

# Detailed model/tool traces live in LangSmith.
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=self-heal
# Set only if the API key belongs to multiple LangSmith workspaces.
# LANGSMITH_WORKSPACE_ID=

# Phase 4 builds the Dockerfile with this image tag.
SELF_HEAL_RUNNER_IMAGE=self-heal-runner:local
```

Copy it to `.env` locally. Keep unused values blank until the phase that needs them; do not invent substitute services or local fallbacks just to make an early smoke test pass.

| Setting | First needed | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY`, `OPENROUTER_AGENT_MODEL` | Phase 1 | Agent model and live tool-call smoke run |
| `ATLAS_URI`, `ATLAS_DATABASE` | Phase 1 | Atlas-backed analyst tables; Phase 3 also uses them for durable history |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | Phase 3 | Model, tool, and task traces |
| `LANGSMITH_WORKSPACE_ID` | Phase 3, only if needed | Select a workspace for a multi-workspace key |
| `OPENROUTER_EVOLUTION_MODEL` | Phase 4 | Scenario, diagnosis, and patch proposals |
| `SELF_HEAL_RUNNER_IMAGE` | Phase 4 | Name of the local candidate-execution image |

## 5. Prepare the external services

### MongoDB Atlas

1. For an event submission, join the **provided Atlas sandbox** through the invitation email and create/use the project and cluster there. The participant guide makes that sandbox mandatory for finalist eligibility. For private practice, use a cluster you control.
2. In Atlas, create a database user for the application. Give it only the access needed for the `self_heal` database. Atlas database users are distinct from Atlas account users.
3. Add the development machine's current IP address to the project's IP access list. If execution later moves to another machine, add that machine's address too.
4. Use **Connect → Drivers → Python** to copy the `mongodb+srv://...` URI. Replace the password placeholder with the database user's password; URL-encode special characters in it. Put the full URI in local `ATLAS_URI` and keep `ATLAS_DATABASE=self_heal`.
5. Do not manually create application collections. Phase 1 creates `analyst_datasets` and `analyst_rows` and verifies the first table; Phase 3 creates `runs`, `eval_cases`, `candidates`, `evaluations`, and `versions` and performs the first linked LangSmith/Atlas run check.

[Atlas connection guide](https://www.mongodb.com/docs/atlas/connect-to-database-deployment/) documents the database-user and IP-access requirements.

### LangSmith

1. Create or sign in to a LangSmith workspace. Create an API key and place it in local `LANGSMITH_API_KEY`.
2. Set `LANGSMITH_TRACING=true` and choose `LANGSMITH_PROJECT=self-heal` (or one consistent project name). If the key belongs to multiple workspaces, set `LANGSMITH_WORKSPACE_ID`.
3. Leave trace instrumentation and trace retrieval to Phase 3. That phase uses the LangSmith SDK with the OpenAI-compatible client and task/tool spans, then stores the trace ID in Atlas. It does not need LangChain/LangGraph, LangSmith Deployments, or a custom trace database.

[LangSmith's OpenAI tracing guide](https://docs.langchain.com/langsmith/trace-openai) documents the tracing variables, `wrap_openai`, and tool spans. The participant resource guide describes a LangSmith credit offer; redeem it separately if useful. The credit offer is not part of the runtime design.

### OpenRouter

1. Create an OpenRouter API key and set `OPENROUTER_API_KEY` in local `.env`.
2. Choose an available **tool-calling** model ID for `OPENROUTER_AGENT_MODEL`. Choose `OPENROUTER_EVOLUTION_MODEL` now or in Phase 4; it may be the same model.
3. Keep the agent model and its settings fixed across baseline and candidate evaluations. Phase 1 implements the thin OpenAI-compatible client; no direct OpenAI key is required for this design.

[OpenRouter's quickstart](https://openrouter.ai/docs/quickstart) documents its OpenAI-compatible API; [tool-calling documentation](https://openrouter.ai/docs/guides/features/tool-calling) covers model capability and request shape. Event credits, if available, are account setup rather than an application dependency.

### Local tools and GitHub

Install Git, Python 3.11 or newer, `uv`, and Docker Desktop on the development machine. Git is needed from the beginning; `uv` installs and locks dependencies in Phase 1. Atlas must be reachable in Phase 1 to seed and read the base table. Docker must be running for generated-candidate execution in Phase 4, but the Dockerfile and image are not built during this bootstrap step. The trusted runner and supervisor keep Atlas, LangSmith, and OpenRouter credentials; a candidate container receives only its task and fixed, dataset-scoped model/table interface.

A GitHub remote can hold the new repository and later reviewable diffs. The first improvement loop does **not** require a GitHub App, personal-access token, Actions workflow, or automatic PR creation. If this is an event submission, follow the participant guide's public-repository requirement when publishing.

## 6. Stop at the phase boundary

The scaffold is ready when the directory layout, README, six-phase plan index, `.gitignore`, and `.env.example` exist; `.env` is ignored; the intended accounts/keys are available; and Git points at the new repository. A brief configuration check may verify that required values are present without printing them.

Then begin [Phase 1](docs/phases/01-base-analyst.md). Its completion checks include Atlas table materialization and the first live model/tool task. [Phase 3](docs/phases/03-tracing-and-atlas.md) owns the first linked LangSmith/Atlas run; [Phase 4](docs/phases/04-eval-creation-and-evolution.md) owns the Docker image and candidate execution. Do not report any of those capabilities as working based on account setup alone.
