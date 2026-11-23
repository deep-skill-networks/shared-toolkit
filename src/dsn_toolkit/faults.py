"""Declarative fault injection (seeded, off by default).

The same mechanism powers break-fix labs, self-paced fault packs and game days. Faults
are applied at named hook points; when no fault is enabled for a point, the wrapped value
passes through untouched.

    faults = FaultSet.from_yaml("faults.yaml")     # private for game days
    chunk_size = faults.apply("retrieval.chunker", {"chunk_size": 800})["chunk_size"]

Learner-facing labs do NOT read a faults.yaml: their faults are compiled into realistic
code. This module is for instructor game days and learner-safe practice packs.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

HOOK_POINTS = {
    "config.load",
    "retrieval.chunker",
    "retrieval.embedder",
    "retrieval.retriever",
    "prompt.builder",
    "prompt.prefix",
    "model.client",
    "tool.client",
    "logger",
    "autoscaler.config",
}

Mutator = Callable[[Any, dict[str, Any], random.Random], Any]


def _override(value: Any, params: dict[str, Any], _rng: random.Random) -> Any:
    if isinstance(value, dict):
        return {**value, **{k: v for k, v in params.items() if k != "inject"}}
    return params.get("value", value)


def _inject_timestamp(value: Any, _params: dict[str, Any], rng: random.Random) -> Any:
    # FS-COST-03: a changing prefix silently defeats prompt/semantic caching.
    return f"[ts={rng.randint(10**9, 2 * 10**9)}] {value}"


MUTATORS: dict[str, Mutator] = {"override": _override, "timestamp": _inject_timestamp}


@dataclass
class Fault:
    id: str
    target: str
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = False
    seed: int = 0

    def __post_init__(self) -> None:
        if self.target not in HOOK_POINTS:
            raise ValueError(f"{self.id}: unknown hook point '{self.target}'")


@dataclass
class FaultSet:
    faults: list[Fault] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> FaultSet:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls([Fault(**f) for f in data.get("faults", [])])

    def active(self, target: str) -> list[Fault]:
        return [f for f in self.faults if f.enabled and f.target == target]

    def apply(self, target: str, value: Any) -> Any:
        for fault in self.active(target):
            mode = "timestamp" if fault.params.get("inject") == "timestamp" else "override"
            value = MUTATORS[mode](value, fault.params, random.Random(fault.seed))
        return value
