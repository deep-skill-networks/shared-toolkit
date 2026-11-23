"""Quiz bank: schema, validation, attempt draws and exporters.

The graded bank lives ONLY in the private `instructor-solutions` repo. Learner repos get
an ungraded `practice/` set. This module turns the bank into:

- Google Forms build files (JSON consumed by ``apps_script/build_forms.gs``)
- GIFT (Moodle-class LMS import) and CSV (review / other LMS)

Item format (YAML list)::

    - id: M01-Q001
      module: M01
      week: 1                 # course week the item is first taught
      pillar: C1              # C1–C6
      bloom: Analyse          # Remember|Understand|Apply|Analyse|Evaluate|Create
      difficulty: medium      # easy|medium|hard
      spaced: true            # eligible as a spaced-review item in later weeks
      stem: "Scenario ..."
      options: {a: "...", b: "...", c: "...", d: "..."}
      correct: b
      explanations: {a: "why a is wrong", b: "why b is right", c: "...", d: "..."}
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

BLOOM = {"Remember", "Understand", "Apply", "Analyse", "Evaluate", "Create"}
DIFFICULTY = {"easy", "medium", "hard"}
PILLARS = {f"C{i}" for i in range(1, 7)}
MODULE_RE = re.compile(r"^(M0[1-8]|P[12])$")


class QuizError(ValueError):
    pass


@dataclass(frozen=True)
class Item:
    id: str
    module: str
    week: int
    pillar: str
    bloom: str
    difficulty: str
    spaced: bool
    stem: str
    options: dict[str, str]
    correct: str
    explanations: dict[str, str]


def _item(raw: dict[str, Any]) -> Item:
    iid = raw.get("id", "<missing id>")
    missing = [
        k
        for k in (
            "id",
            "module",
            "week",
            "pillar",
            "bloom",
            "difficulty",
            "stem",
            "options",
            "correct",
            "explanations",
        )
        if k not in raw
    ]
    if missing:
        raise QuizError(f"{iid}: missing fields {missing}")
    if not MODULE_RE.match(str(raw["module"])):
        raise QuizError(f"{iid}: module must be M01–M08 or P1/P2")
    if raw["pillar"] not in PILLARS:
        raise QuizError(f"{iid}: pillar must be one of C1–C6")
    if raw["bloom"] not in BLOOM:
        raise QuizError(f"{iid}: bloom must be one of {sorted(BLOOM)}")
    if raw["difficulty"] not in DIFFICULTY:
        raise QuizError(f"{iid}: difficulty must be easy, medium or hard")
    options = {str(k): str(v) for k, v in raw["options"].items()}
    if not 2 <= len(options) <= 6:
        raise QuizError(f"{iid}: needs 2–6 options")
    if raw["correct"] not in options:
        raise QuizError(f"{iid}: correct answer '{raw['correct']}' is not an option")
    explanations = {str(k): str(v) for k, v in raw["explanations"].items()}
    if set(explanations) != set(options):
        raise QuizError(f"{iid}: every option needs an explanation (the feedback is the learning)")
    if len(set(options.values())) != len(options):
        raise QuizError(f"{iid}: duplicate option text")
    return Item(
        id=str(raw["id"]),
        module=str(raw["module"]),
        week=int(raw["week"]),
        pillar=raw["pillar"],
        bloom=raw["bloom"],
        difficulty=raw["difficulty"],
        spaced=bool(raw.get("spaced", True)),
        stem=str(raw["stem"]).strip(),
        options=options,
        correct=str(raw["correct"]),
        explanations=explanations,
    )


def load_bank(*paths: str | Path) -> list[Item]:
    items: list[Item] = []
    for path in paths:
        p = Path(path)
        files = sorted(p.rglob("*.yaml")) if p.is_dir() else [p]
        for f in files:
            for raw in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
                items.append(_item(raw))
    ids = [i.id for i in items]
    dupes = sorted({x for x in ids if ids.count(x) > 1})
    if dupes:
        raise QuizError(f"duplicate item ids: {dupes}")
    return items


# ---------------------------------------------------------------- weekly attempts


@dataclass
class Attempt:
    week: int
    number: int
    items: list[Item]


def draw_attempts(
    bank: list[Item], week: int, per_attempt: int = 10, spaced: int = 3, seed: int = 0
) -> tuple[Attempt, Attempt]:
    """Two attempts for a week, each `per_attempt` new items + `spaced` review items from
    earlier weeks. The two attempts share as few items as the bank allows, so a second
    attempt is a genuine re-test rather than a memory test."""
    rng = random.Random(f"{seed}-{week}")
    current = [i for i in bank if i.week == week]
    if len(current) < per_attempt:
        raise QuizError(f"week {week}: only {len(current)} items, need at least {per_attempt}")
    rng.shuffle(current)
    first = current[:per_attempt]
    rest = current[per_attempt:]
    second = rest[:per_attempt]
    if len(second) < per_attempt:  # top up with first-attempt items when the bank is small
        second += first[: per_attempt - len(second)]
    earlier = [i for i in bank if i.week < week and i.spaced]
    rng.shuffle(earlier)
    sp1, sp2 = earlier[:spaced], earlier[spaced : 2 * spaced] or earlier[:spaced]
    return Attempt(week, 1, first + sp1), Attempt(week, 2, second + sp2)


# ---------------------------------------------------------------- exporters


def _gift_escape(text: str) -> str:
    for ch in ("\\", "~", "=", "#", "{", "}", ":"):
        text = text.replace(ch, "\\" + ch)
    return text.replace("\n", "\\n")


def to_gift(items: list[Item]) -> str:
    out = []
    for it in items:
        lines = [f"::{_gift_escape(it.id)}::{_gift_escape(it.stem)} {{"]
        for key, text in it.options.items():
            mark = "=" if key == it.correct else "~"
            lines.append(f"\t{mark}{_gift_escape(text)}#{_gift_escape(it.explanations[key])}")
        lines.append("}")
        out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


CSV_FIELDS = [
    "question",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct",
    "explanation",
    "bloom",
    "module",
    "difficulty",
    "id",
    "pillar",
    "week",
]


def to_csv(items: list[Item]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    w.writeheader()
    for it in items:
        keys = list(it.options)
        row = {
            "question": it.stem,
            "correct": it.correct,
            "bloom": it.bloom,
            "module": it.module,
            "difficulty": it.difficulty,
            "id": it.id,
            "pillar": it.pillar,
            "week": it.week,
            "explanation": " | ".join(f"{k}: {it.explanations[k]}" for k in keys),
        }
        for letter in "abcd":
            row[f"option_{letter}"] = it.options.get(letter, "")
        w.writerow(row)
    return buf.getvalue()


def to_forms_json(attempt: Attempt, title_prefix: str = "Weekly quiz") -> dict[str, Any]:
    """Payload for apps_script/build_forms.gs. Google Forms shows feedback per question
    (correct / incorrect), so the incorrect feedback carries every option's explanation."""
    items = []
    for it in attempt.items:
        items.append(
            {
                "id": it.id,
                "title": it.stem,
                "choices": [
                    {"text": t, "isCorrect": k == it.correct} for k, t in it.options.items()
                ],
                "points": 1,
                "feedbackCorrect": it.explanations[it.correct],
                "feedbackIncorrect": "\n".join(
                    f"{t}: {it.explanations[k]}" for k, t in it.options.items()
                ),
            }
        )
    return {
        "title": f"{title_prefix} — week {attempt.week} — attempt {attempt.number}",
        "description": "Scenario questions. Your score and the explanations appear as soon as "
        "you submit. Your better attempt counts.",
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dsn-quiz")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate one or more bank files or folders")
    v.add_argument("paths", nargs="+")
    e = sub.add_parser("export", help="export a bank as GIFT or CSV")
    e.add_argument("paths", nargs="+")
    e.add_argument("--format", choices=["gift", "csv"], required=True)
    d = sub.add_parser("draw", help="draw two attempts for a week and write Forms JSON")
    d.add_argument("paths", nargs="+")
    d.add_argument("--week", type=int, required=True)
    d.add_argument("--per-attempt", type=int, default=10)
    d.add_argument("--spaced", type=int, default=3)
    d.add_argument("--seed", type=int, default=0)
    d.add_argument("--out", default="exports")
    args = ap.parse_args(argv)
    try:
        bank = load_bank(*args.paths)
    except QuizError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    if args.cmd == "validate":
        print(f"OK: {len(bank)} items")
    elif args.cmd == "export":
        sys.stdout.write(to_gift(bank) if args.format == "gift" else to_csv(bank))
    else:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for attempt in draw_attempts(bank, args.week, args.per_attempt, args.spaced, args.seed):
            path = out / f"week{args.week:02d}-attempt{attempt.number}.json"
            path.write_text(json.dumps(to_forms_json(attempt), indent=2, ensure_ascii=False))
            print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
