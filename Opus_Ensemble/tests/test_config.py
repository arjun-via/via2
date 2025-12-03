"""
Tests for config.py - Configuration management.
"""

import os
import pytest
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    ModelMode,
    ModelConfig,
    EnsembleConfig,
    get_config,
    get_test_config,
    MODELS,
    STRATEGY_SYSTEM_PROMPTS,
)


class TestModelMode:
    """Tests for ModelMode enum."""

    def test_production_mode_value(self):
        """Production mode has correct value."""
        assert ModelMode.PRODUCTION.value == "opus"

    def test_test_mode_value(self):
        """Test mode has correct value."""
        assert ModelMode.TEST.value == "test"

    def test_only_two_modes(self):
        """Only production and test modes exist."""
        modes = list(ModelMode)
        assert len(modes) == 2
        assert ModelMode.PRODUCTION in modes
        assert ModelMode.TEST in modes


class TestModelConfig:
    """Tests for ModelConfig dataclass."""

    def test_production_model_config(self):
        """Production model config is correct."""
        config = MODELS[ModelMode.PRODUCTION]
        assert config.model_id == "claude-opus-4-5-20250514"
        assert config.provider == "anthropic"
        assert config.base_url == "https://api.anthropic.com/v1"
        assert config.api_key_env == "ANTHROPIC_API_KEY"
        assert config.input_price_per_m == 5.0
        assert config.output_price_per_m == 25.0

    def test_test_model_config(self):
        """Test model config uses gpt-oss-120b via OpenRouter."""
        config = MODELS[ModelMode.TEST]
        assert config.model_id == "openai/gpt-oss-120b"
        assert config.provider == "openrouter"
        assert config.base_url == "https://openrouter.ai/api/v1"
        assert config.api_key_env == "OPENROUTER_API_KEY"
        assert config.input_price_per_m == 0.0  # Free via Cerebras
        assert config.output_price_per_m == 0.0

    def test_api_key_from_env(self):
        """API key is read from environment variable."""
        with patch.dict(os.environ, {"TEST_API_KEY": "test-key-123"}):
            config = ModelConfig(
                model_id="test",
                provider="test",
                base_url="http://test",
                api_key_env="TEST_API_KEY",
                input_price_per_m=0.0,
                output_price_per_m=0.0,
            )
            assert config.api_key == "test-key-123"

    def test_api_key_missing_raises(self):
        """Missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            config = ModelConfig(
                model_id="test",
                provider="test",
                base_url="http://test",
                api_key_env="NONEXISTENT_API_KEY",
                input_price_per_m=0.0,
                output_price_per_m=0.0,
            )
            with pytest.raises(ValueError, match="Missing API key"):
                _ = config.api_key


class TestEnsembleConfig:
    """Tests for EnsembleConfig dataclass."""

    def test_default_config_is_production(self):
        """Default config uses production mode."""
        config = EnsembleConfig()
        assert config.mode == ModelMode.PRODUCTION
        assert config.model.model_id == "claude-opus-4-5-20250514"

    def test_default_parallel_instances(self):
        """Default is 40 parallel instances."""
        config = EnsembleConfig()
        assert config.num_parallel_instances == 40

    def test_strategy_distribution_sums_to_40(self):
        """Strategy distribution sums to 40."""
        config = EnsembleConfig()
        total = sum(config.strategy_distribution.values())
        assert total == 40

    def test_all_strategies_have_prompts(self):
        """All strategies in distribution have prompts."""
        config = EnsembleConfig()
        for strategy_name in config.strategy_distribution.keys():
            assert strategy_name in STRATEGY_SYSTEM_PROMPTS

    def test_high_temperature_strategy(self):
        """High temperature strategy uses higher temperature."""
        config = EnsembleConfig()
        assert config.strategy_temperatures["high_temperature"] == 0.8
        assert config.strategy_temperatures["minimal"] == 0.0


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_config_production(self):
        """Explicit production mode works."""
        config = get_config(ModelMode.PRODUCTION)
        assert config.mode == ModelMode.PRODUCTION
        assert config.model.model_id == "claude-opus-4-5-20250514"

    def test_get_config_test(self):
        """Explicit test mode works."""
        config = get_config(ModelMode.TEST)
        assert config.mode == ModelMode.TEST
        assert config.model.model_id == "openai/gpt-oss-120b"

    def test_env_var_opus(self):
        """Environment variable 'opus' selects production."""
        with patch.dict(os.environ, {"OPUS_ENSEMBLE_MODEL": "opus"}):
            config = get_config()
            assert config.mode == ModelMode.PRODUCTION

    def test_env_var_test(self):
        """Environment variable 'test' selects test mode."""
        with patch.dict(os.environ, {"OPUS_ENSEMBLE_MODEL": "test"}):
            config = get_config()
            assert config.mode == ModelMode.TEST

    def test_env_var_production_alias(self):
        """Environment variable 'production' selects production."""
        with patch.dict(os.environ, {"OPUS_ENSEMBLE_MODEL": "production"}):
            config = get_config()
            assert config.mode == ModelMode.PRODUCTION

    def test_env_var_testing_alias(self):
        """Environment variable 'testing' selects test mode."""
        with patch.dict(os.environ, {"OPUS_ENSEMBLE_MODEL": "testing"}):
            config = get_config()
            assert config.mode == ModelMode.TEST

    def test_default_is_production(self):
        """No env var defaults to production."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove OPUS_ENSEMBLE_MODEL if it exists
            os.environ.pop("OPUS_ENSEMBLE_MODEL", None)
            config = get_config()
            assert config.mode == ModelMode.PRODUCTION


class TestGetTestConfig:
    """Tests for get_test_config function."""

    def test_uses_test_mode(self):
        """Test config uses test mode."""
        config = get_test_config()
        assert config.mode == ModelMode.TEST
        assert config.model.model_id == "openai/gpt-oss-120b"

    def test_reduced_instances(self):
        """Test config uses fewer parallel instances."""
        config = get_test_config()
        assert config.num_parallel_instances == 5

    def test_reduced_strategies(self):
        """Test config uses fewer strategies."""
        config = get_test_config()
        total = sum(config.strategy_distribution.values())
        assert total == 5

    def test_no_high_temperature(self):
        """Test config disables high temperature strategy."""
        config = get_test_config()
        assert config.strategy_distribution.get("high_temperature", 0) == 0


class TestStrategyPrompts:
    """Tests for strategy system prompts."""

    def test_all_five_strategies_have_prompts(self):
        """All 5 strategies have system prompts."""
        expected_strategies = [
            "minimal",
            "extended_thinking",
            "test_driven",
            "refactor_safe",
            "high_temperature",
        ]
        for strategy in expected_strategies:
            assert strategy in STRATEGY_SYSTEM_PROMPTS
            assert len(STRATEGY_SYSTEM_PROMPTS[strategy]) > 0

    def test_minimal_strategy_content(self):
        """Minimal strategy focuses on small patches."""
        prompt = STRATEGY_SYSTEM_PROMPTS["minimal"]
        assert "smallest" in prompt.lower() or "minimum" in prompt.lower()

    def test_extended_thinking_strategy_content(self):
        """Extended thinking strategy emphasizes reasoning."""
        prompt = STRATEGY_SYSTEM_PROMPTS["extended_thinking"]
        assert "analyze" in prompt.lower() or "reasoning" in prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
