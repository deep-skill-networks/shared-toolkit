"""Model configuration: provider and model in ONE place, with a local fallback.

A lab's ``config/models.yaml`` looks like::

    default: hosted            # profile to use when its key is available
    fallback: local            # profile to use otherwise (must not need a key)
    profiles:
      hosted:
        provider: openai-compatible
        model: "<provider-model-id-with-a-date>"   # never a moving alias
        api_key_env: COURSE_API_KEY
        base_url: null
        temperature: 0.0
        max_tokens: 512
        max_cost_inr_per_run: 100
      local:
        provider: ollama
        model: "llama3.2:3b"
        base_url: http://localhost:11434
        temperature: 0.0
        max_tokens: 512

Guardrails taught by the course and enforced here:
- moving aliases (``latest``, ``-latest``) are rejected (FS-MOD-02),
- temperature must be within [0, 1] for course labs (FS-MOD-01),
- environment overrides are explicit and validated, never silent.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ALIAS_PATTERN = re.compile(r"(^|[-:/])latest$", re.IGNORECASE)
PROFILE_ENV = "DSN_MODEL_PROFILE"


class ConfigError(ValueError):
    """Raised when a models.yaml file is invalid or unsafe."""


@dataclass(frozen=True)
class ModelProfile:
    name: str
    provider: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 512
    base_url: str | None = None
    api_key_env: str | None = None
    max_cost_inr_per_run: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def needs_key(self) -> bool:
        return bool(self.api_key_env)

    def key_available(self, environ: dict[str, str] | None = None) -> bool:
        env = os.environ if environ is None else environ
        return not self.needs_key or bool(env.get(self.api_key_env or ""))


_KNOWN = {
    "provider",
    "model",
    "temperature",
    "max_tokens",
    "base_url",
    "api_key_env",
    "max_cost_inr_per_run",
}


def _profile(name: str, raw: dict[str, Any]) -> ModelProfile:
    if not isinstance(raw, dict):
        raise ConfigError(f"profile '{name}' must be a mapping")
    for required in ("provider", "model"):
        if not raw.get(required):
            raise ConfigError(f"profile '{name}' is missing '{required}'")
    model = str(raw["model"])
    if ALIAS_PATTERN.search(model):
        raise ConfigError(
            f"profile '{name}' uses a moving alias '{model}'. Pin a dated model version "
            "so the provider can't change behaviour without a deploy (FS-MOD-02)."
        )
    temperature = float(raw.get("temperature", 0.0))
    if not 0.0 <= temperature <= 1.0:
        raise ConfigError(
            f"profile '{name}' has temperature {temperature}; "
            "course labs allow 0.0–1.0 (FS-MOD-01)."
        )
    max_tokens = int(raw.get("max_tokens", 512))
    if max_tokens <= 0:
        raise ConfigError(f"profile '{name}' has non-positive max_tokens")
    return ModelProfile(
        name=name,
        provider=str(raw["provider"]),
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        base_url=raw.get("base_url"),
        api_key_env=raw.get("api_key_env"),
        max_cost_inr_per_run=raw.get("max_cost_inr_per_run"),
        extra={k: v for k, v in raw.items() if k not in _KNOWN},
    )


@dataclass(frozen=True)
class ModelsConfig:
    default: str
    fallback: str
    profiles: dict[str, ModelProfile]

    def select(self, environ: dict[str, str] | None = None) -> ModelProfile:
        """Pick the profile to use.

        Order: an explicit DSN_MODEL_PROFILE (validated), then the default profile if its key
        is available, then the fallback. The choice is deterministic and explainable.
        """
        env = os.environ if environ is None else environ
        requested = env.get(PROFILE_ENV)
        if requested:
            if requested not in self.profiles:
                raise ConfigError(
                    f"{PROFILE_ENV}={requested!r} is not a profile in models.yaml "
                    f"(have: {', '.join(sorted(self.profiles))})"
                )
            profile = self.profiles[requested]
            if not profile.key_available(env):
                raise ConfigError(
                    f"profile '{requested}' needs ${profile.api_key_env}, which is not set"
                )
            return profile
        default = self.profiles[self.default]
        if default.key_available(env):
            return default
        return self.profiles[self.fallback]


def load_models_config(path: str | Path = "config/models.yaml") -> ModelsConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw_profiles = data.get("profiles") or {}
    if not raw_profiles:
        raise ConfigError("models.yaml has no profiles")
    profiles = {name: _profile(name, raw) for name, raw in raw_profiles.items()}
    default = data.get("default")
    fallback = data.get("fallback")
    for label, value in (("default", default), ("fallback", fallback)):
        if value not in profiles:
            raise ConfigError(f"'{label}: {value}' is not a defined profile")
    if profiles[fallback].needs_key:
        raise ConfigError("the fallback profile must not need an API key, so every lab runs at ₹0")
    return ModelsConfig(default=default, fallback=fallback, profiles=profiles)
