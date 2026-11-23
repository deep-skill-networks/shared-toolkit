# shared-toolkit

Reusable building blocks for every lab and capstone in the Deep Skill Networks AI Engineering & FDE Program. Labs import it as a **pinned** package; never copy its code into a module repo.

| Module | What it gives you | Course link |
|---|---|---|
| `dsn_toolkit.config` | Provider and model in one `config/models.yaml`, a free local fallback, and guardrails: no moving model aliases, temperature 0–1, explicit overrides only | FS-MOD-01, FS-MOD-02 |
| `dsn_toolkit.evals` | Eval cases with simple checks, pass rates **with 95% confidence intervals**, per-segment results (e.g. English vs Hinglish), and a CI gate | M04, FS-EVAL-04 |
| `dsn_toolkit.quiz` | Quiz-bank schema and validation, two different weekly attempts plus spaced items, exports to Google Forms, GIFT and CSV | Assessment |
| `dsn_toolkit.faults` | Seeded, off-by-default fault injection at named hook points | Break-fix labs, game days |
| `scripts/provision.py` | Creates each learner's private repos in the org from a template (dry run by default) | Onboarding |
| `apps_script/build_forms.gs` | Builds a Google Forms quiz from an exported attempt | Assessment |

## Install

```bash
# in a lab or capstone repo (pin a tag; never track main)
uv add "dsn-toolkit @ git+https://github.com/deep-skill-networks/shared-toolkit@v0.1.0"
```

Requires Python 3.11+. The only runtime dependency is PyYAML.

## Quick start

```python
from dsn_toolkit.config import load_models_config

profile = load_models_config("config/models.yaml").select()
print(profile.name, profile.model)  # hosted if COURSE_API_KEY is set, otherwise local (₹0)

from dsn_toolkit.evals import load_cases, run_suite, gate

report = run_suite(load_cases("evals/golden.yaml"), my_system)
print(report.summary())  # pass rate, 95% CI, per-segment rates, failures
assert gate(report, min_pass_rate=0.8).ok
```

```bash
dsn-quiz validate quizzes/                         # schema + duplicate checks
dsn-quiz draw quizzes/ --week 3 --seed 2027        # two attempts -> exports/*.json for Google Forms
dsn-quiz export quizzes/ --format gift > m01.gift  # Moodle-class import
dsn-eval gate results.jsonl --min-pass-rate 0.8    # CI gate on recorded results
```

See [`examples/`](examples/) for a `models.yaml`, eval cases and practice quiz items.

## Building weekly quiz forms

1. In the private `instructor-solutions` repo, run `dsn-quiz draw` for the week.
2. Upload the two JSON files to Google Drive.
3. Run `buildQuizFromDriveFile(fileId, gradebookSheetId)` from [`apps_script/build_forms.gs`](apps_script/build_forms.gs) once per file.
4. Link both forms from the week's Tagmango lesson. The gradebook sheet keeps the better attempt.

## What's next
- `tracing` (OpenTelemetry setup) — before M06
- `replay` (traffic replay with recorded model responses) — before M03
- Practice fault packs — from M03 ([`faultpacks/`](faultpacks/README.md))

## Development

```bash
uv venv && uv pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest
```

Releases are tagged `vX.Y.Z`. Labs pin a tag, and each cohort's repos are tagged `cohort-YYYY-NN`, so changes on `main` never break a running cohort.

---

## About the mentor

**Sanjay Negi** brings 23+ years of industry experience and helps experienced software engineers and technology leaders transition into high-value AI roles, including **AI Engineer**, **Forward Deployed Engineer** and **GenAI Architect**. He has trained more than 1,100 experienced engineers.

<p align="center">
  <img src="https://raw.githubusercontent.com/deep-skill-networks/course-hub/main/assets/brand/skillupwithsanjay.png" alt="SkillUp with Sanjay logo" width="60">
</p>

<p align="center"><strong>#SkillUpWithSanjay</strong></p>

<p align="center">
  <a href="https://learn.sanjaynegi.in/web/checkout/6afd228779901d1204871d43" target="_blank" rel="noopener noreferrer"><strong>Join the program</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="https://www.sanjaynegi.in" target="_blank" rel="noopener noreferrer">Website</a>
  &nbsp;&middot;&nbsp;
  <a href="https://www.linkedin.com/in/sanjay-negi-ai/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
</p>
