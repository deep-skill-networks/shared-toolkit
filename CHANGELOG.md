# Changelog

## 0.1.0 — unreleased
- `config`: models.yaml loader with local fallback; rejects moving aliases and out-of-range temperature.
- `evals`: checks, Wilson and bootstrap intervals, per-segment rates, CI gate, `dsn-eval` CLI.
- `quiz`: schema validation, two-attempt weekly draws with spaced items, GIFT/CSV/Google Forms export, `dsn-quiz` CLI.
- `faults`: seeded fault injection at named hook points.
- `scripts/provision.py`: learner repo provisioning from templates (dry run by default).
- `apps_script/build_forms.gs`: Google Forms quiz builder.
