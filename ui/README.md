# Self-Heal UI demo

This is a dependency-free, static product demo for the inventory analyst. It is intentionally
separate from the current Python CLI: the checked-in implementation has Phases 1–2, while the
proposal, evaluation-history, and activation flow shown here is illustrative of later phases.

Preview it from the repository root:

```sh
python3 -m http.server 4173 --directory ui
```

Then open [http://127.0.0.1:4173](http://127.0.0.1:4173).

The displayed 512-row bulk-case totals come from the deterministic scenario in
`evals/analyst/scenarios.yaml`; the reference image's 240-row values are deliberately not used.
