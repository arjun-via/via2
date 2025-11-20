import os
from copy import deepcopy
from typing import Any, Dict, Iterable, Mapping, MutableMapping

import yaml


REQUIRED_MODELS = ["orchestrator", "context", "repro", "engineering", "review"]


def _infer_type(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _set_nested(config: MutableMapping[str, Any], keys: Iterable[str], value: Any) -> None:
    keys = list(keys)
    current = config
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], MutableMapping):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def load_config(config_path: str = "config/config.yaml", env: Mapping[str, str] | None = None) -> Dict[str, Any]:
    """Load YAML config and apply environment overrides.

    Overrides use the pattern ALO_FOO__bar__baz=value -> config["foo"]["bar"]["baz"].
    """
    env = env or os.environ
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    config = deepcopy(data)
    prefix = "ALO_"
    for key, value in env.items():
        if not key.startswith(prefix):
            continue
        path = key[len(prefix) :].lower().split("__")
        _set_nested(config, path, _infer_type(value))

    _validate_config(config)
    return config


def _validate_config(config: Mapping[str, Any]) -> None:
    models = config.get("models", {})
    if not isinstance(models, Mapping):
        raise ValueError("`models` section missing or invalid in config")

    for model_name in REQUIRED_MODELS:
        model_conf = models.get(model_name)
        if not isinstance(model_conf, Mapping) or "id" not in model_conf:
            raise ValueError(f"Missing model config for {model_name}")

    # optional logging
    if "logging" in config and not isinstance(config["logging"], Mapping):
        raise ValueError("`logging` section must be a mapping if provided")
