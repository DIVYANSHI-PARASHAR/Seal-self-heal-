# Self-Heal

Self-Heal is a task-adaptive agent harness. A trusted supervisor turns observed task limitations into reproducible evaluations, proposes a reusable harness change, tests it against existing and fresh cases, and activates only a validated version.

The first use case is a small Python analyst for structured tables. The editable harness owns its tools and context policy. The protected supervisor owns the oracle, evaluation limits, trace integration, and version decisions.

MongoDB Atlas will hold the structured analyst tables and compact run, case, candidate, evaluation, and version records. A trusted table interface will let each run read only its assigned dataset without exposing Atlas credentials to generated harness code. LangSmith will hold detailed model and tool traces linked to those records. OpenRouter will supply model calls. Candidate code will run in a local Docker container; Git will pin each evaluated version.

**Status:** repository scaffold and service configuration only. Harness behavior, evaluations, tracing, storage, and the improvement loop are built in the six phases described in [docs/build-plan.md](docs/build-plan.md).

See [SETUP.md](SETUP.md) for account and environment setup.
