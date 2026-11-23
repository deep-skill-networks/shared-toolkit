import pytest
import yaml

from dsn_toolkit.config import ConfigError, load_models_config

BASE = {
    "default": "hosted",
    "fallback": "local",
    "profiles": {
        "hosted": {
            "provider": "openai-compatible",
            "model": "vendor-model-2026-09-01",
            "api_key_env": "COURSE_API_KEY",
            "temperature": 0.0,
        },
        "local": {"provider": "ollama", "model": "llama3.2:3b", "temperature": 0.0},
    },
}


def write(tmp_path, data):
    p = tmp_path / "models.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_falls_back_to_local_without_key(tmp_path):
    cfg = load_models_config(write(tmp_path, BASE))
    assert cfg.select({}).name == "local"


def test_uses_hosted_when_key_present(tmp_path):
    cfg = load_models_config(write(tmp_path, BASE))
    assert cfg.select({"COURSE_API_KEY": "x"}).name == "hosted"


def test_explicit_profile_must_exist(tmp_path):
    cfg = load_models_config(write(tmp_path, BASE))
    with pytest.raises(ConfigError):
        cfg.select({"DSN_MODEL_PROFILE": "nope"})


def test_explicit_profile_needs_its_key(tmp_path):
    cfg = load_models_config(write(tmp_path, BASE))
    with pytest.raises(ConfigError):
        cfg.select({"DSN_MODEL_PROFILE": "hosted"})


@pytest.mark.parametrize("alias", ["gpt-latest", "llama3:latest", "model/latest", "LATEST"])
def test_rejects_moving_aliases(tmp_path, alias):
    data = yaml.safe_load(yaml.safe_dump(BASE))
    data["profiles"]["hosted"]["model"] = alias
    with pytest.raises(ConfigError, match="alias"):
        load_models_config(write(tmp_path, data))


def test_rejects_out_of_range_temperature(tmp_path):
    data = yaml.safe_load(yaml.safe_dump(BASE))
    data["profiles"]["hosted"]["temperature"] = 1.2
    with pytest.raises(ConfigError, match="FS-MOD-01"):
        load_models_config(write(tmp_path, data))


def test_fallback_must_be_free(tmp_path):
    data = yaml.safe_load(yaml.safe_dump(BASE))
    data["fallback"] = "hosted"
    with pytest.raises(ConfigError, match="fallback"):
        load_models_config(write(tmp_path, data))


def test_example_file_is_valid():
    cfg = load_models_config("examples/models.yaml")
    assert cfg.select({}).provider == "ollama"
