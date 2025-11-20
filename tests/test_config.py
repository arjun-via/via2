import os
import textwrap

import pytest

from alo.config.loader import load_config


def test_load_config_with_env_override(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            models:
              orchestrator: {id: "anthropic/claude-sonnet-4.5", temperature: 0}
              context: {id: "google/gemini-3", temperature: 0}
              repro: {id: "openai/gpt-5.1", temperature: 0}
              engineering: {id: "cerebras/glm-4.6", temperature: 0}
              review: {id: "openrouter/kimi-k2", temperature: 0}
            logging: {level: INFO}
            """
        ).strip()
    )
    monkeypatch.setenv("ALO_MODELS__orchestrator__temperature", "0.3")

    config = load_config(str(config_path))

    assert config["models"]["orchestrator"]["temperature"] == 0.3
    assert config["models"]["review"]["id"] == "openrouter/kimi-k2"


def test_load_config_missing_required_section(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            models:
              orchestrator: {id: "anthropic/claude-sonnet-4.5", temperature: 0}
            """
        ).strip()
    )

    with pytest.raises(ValueError):
        load_config(str(config_path))


def test_load_config_accepts_pricing(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            models:
              orchestrator: {id: "anthropic/claude-sonnet-4.5", temperature: 0, pricing: {prompt: 0.1, completion: 0.2}}
              context: {id: "google/gemini-3", temperature: 0}
              repro: {id: "openai/gpt-5.1", temperature: 0}
              engineering: {id: "cerebras/glm-4.6", temperature: 0}
              review: {id: "openrouter/kimi-k2", temperature: 0}
            """
        ).strip()
    )

    config = load_config(str(config_path))
    assert config["models"]["orchestrator"]["pricing"]["prompt"] == 0.1
