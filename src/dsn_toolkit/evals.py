"""A small eval harness that reports uncertainty and gates CI.

Why confidence intervals: with 30 cases, a pass rate of 0.80 has a 95% interval of roughly
0.63–0.90. Deciding between two prompts on that is noise (FS-EVAL-04). The harness reports
the interval with every number so learners see it.

Usage::

    from dsn_toolkit.evals import EvalCase, run_suite, gate
    cases = load_cases("evals/golden.yaml")
    report = run_suite(cases, my_system)          # my_system(input) -> str
    assert gate(report, min_pass_rate=0.8).ok
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

Z95 = 1.959963984540054


def wilson_interval(passes: int, n: int, z: float = Z95) -> tuple[float, float]:
    """95% Wilson score interval for a pass rate. Well behaved at small n and at 0 or 1."""
    if n <= 0:
        return (0.0, 1.0)
    p = passes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo = 0.0 if passes == 0 else max(0.0, centre - half)
    hi = 1.0 if passes == n else min(1.0, centre + half)
    return (lo, hi)


def bootstrap_mean_ci(
    values: list[float], iterations: int = 2000, seed: int = 0, alpha: float = 0.05
) -> tuple[float, float]:
    """Percentile bootstrap interval for a mean score (e.g. judge scores 1–5)."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(iterations))
    lo = means[int((alpha / 2) * iterations)]
    hi = means[min(iterations - 1, int((1 - alpha / 2) * iterations))]
    return (lo, hi)


# ---------------------------------------------------------------- checks

Check = Callable[[str, dict[str, Any]], bool]


def _contains(output: str, arg: Any) -> bool:
    return all(str(a).lower() in output.lower() for a in (arg if isinstance(arg, list) else [arg]))


def _not_contains(output: str, arg: Any) -> bool:
    items = arg if isinstance(arg, list) else [arg]
    return not any(str(a).lower() in output.lower() for a in items)


def _regex(output: str, arg: Any) -> bool:
    return re.search(str(arg), output) is not None


def _max_chars(output: str, arg: Any) -> bool:
    return len(output) <= int(arg)


def _json_keys(output: str, arg: Any) -> bool:
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return False
    return isinstance(data, dict) and all(k in data for k in arg)


CHECKS: dict[str, Callable[[str, Any], bool]] = {
    "contains": _contains,
    "not_contains": _not_contains,
    "regex": _regex,
    "max_chars": _max_chars,
    "json_keys": _json_keys,
}


@dataclass
class EvalCase:
    id: str
    input: Any
    checks: dict[str, Any] = field(default_factory=dict)
    segment: str = "all"  # e.g. language or customer tier, for per-segment rates
    tags: list[str] = field(default_factory=list)


@dataclass
class CaseResult:
    id: str
    segment: str
    passed: bool
    failed_checks: list[str]
    output: str


@dataclass
class Report:
    results: list[CaseResult]

    @property
    def n(self) -> int:
        return len(self.results)

    @property
    def passes(self) -> int:
        return sum(r.passed for r in self.results)

    @property
    def pass_rate(self) -> float:
        return self.passes / self.n if self.n else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson_interval(self.passes, self.n)

    def by_segment(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for seg in sorted({r.segment for r in self.results}):
            rs = [r for r in self.results if r.segment == seg]
            p = sum(r.passed for r in rs)
            lo, hi = wilson_interval(p, len(rs))
            out[seg] = {"n": len(rs), "pass_rate": p / len(rs), "ci_low": lo, "ci_high": hi}
        return out

    def summary(self) -> dict[str, Any]:
        lo, hi = self.interval
        return {
            "n": self.n,
            "passes": self.passes,
            "pass_rate": round(self.pass_rate, 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "segments": self.by_segment(),
            "failures": [
                {"id": r.id, "failed_checks": r.failed_checks} for r in self.results if not r.passed
            ],
        }


def load_cases(path: str | Path) -> list[EvalCase]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    cases = []
    seen = set()
    for item in raw:
        if item["id"] in seen:
            raise ValueError(f"duplicate case id {item['id']}")
        seen.add(item["id"])
        unknown = set(item.get("checks", {})) - set(CHECKS)
        if unknown:
            raise ValueError(f"case {item['id']} uses unknown checks: {sorted(unknown)}")
        cases.append(EvalCase(**item))
    return cases


def run_suite(cases: Iterable[EvalCase], system: Callable[[Any], str]) -> Report:
    results = []
    for case in cases:
        output = system(case.input)
        failed = [name for name, arg in case.checks.items() if not CHECKS[name](output, arg)]
        results.append(CaseResult(case.id, case.segment, not failed, failed, output))
    return Report(results)


@dataclass
class GateResult:
    ok: bool
    message: str


def gate(report: Report, min_pass_rate: float, use_lower_bound: bool = False) -> GateResult:
    """Release gate. With use_lower_bound=True the gate passes only if the whole 95% interval
    clears the bar, which is stricter and protects against small, lucky eval runs."""
    lo, hi = report.interval
    value = lo if use_lower_bound else report.pass_rate
    label = "CI lower bound" if use_lower_bound else "pass rate"
    msg = (
        f"{label} {value:.3f} (pass rate {report.pass_rate:.3f}, 95% CI {lo:.3f}–{hi:.3f}, "
        f"n={report.n}) vs threshold {min_pass_rate:.3f}"
    )
    return GateResult(value >= min_pass_rate, msg)


def main(argv: list[str] | None = None) -> int:
    """`dsn-eval gate results.jsonl --min-pass-rate 0.8` — results are {"id","passed","segment"}."""
    ap = argparse.ArgumentParser(prog="dsn-eval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate", help="gate CI on a JSONL file of case results")
    g.add_argument("results")
    g.add_argument("--min-pass-rate", type=float, required=True)
    g.add_argument("--use-lower-bound", action="store_true")
    args = ap.parse_args(argv)
    rows = [
        json.loads(line) for line in Path(args.results).read_text().splitlines() if line.strip()
    ]
    report = Report(
        [CaseResult(r["id"], r.get("segment", "all"), bool(r["passed"]), [], "") for r in rows]
    )
    result = gate(report, args.min_pass_rate, args.use_lower_bound)
    print(json.dumps(report.summary(), indent=2))
    print(("PASS: " if result.ok else "FAIL: ") + result.message)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
