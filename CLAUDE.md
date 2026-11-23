# Conventions for Claude sessions in shared-toolkit

Follow the org conventions in [`course-hub/CLAUDE.md`](https://github.com/deep-skill-networks/course-hub/blob/main/CLAUDE.md). Additionally:

- This package is imported by every lab and capstone. Keep the public API stable within a minor version; breaking changes need a new minor version and a CHANGELOG entry.
- Keep runtime dependencies minimal (PyYAML only today). Anything heavier goes behind an optional extra.
- Every change needs tests; `ruff check`, `ruff format --check` and `pytest` must pass.
- **This repo is public.** Never add graded quiz items, answer keys, hidden tests, game-day faults, learner data or secrets. Anything private belongs in `instructor-solutions` or `gameday-scenarios`.
- Model IDs in examples are placeholders or open local models; never hard-code a hosted model alias.
