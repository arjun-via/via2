"""
=============================================================================
ALO v2.0 Configuration
=============================================================================

Model configurations and API settings for the Opus-orchestrated pipeline.

MODELS:
- Opus 4.5: Orchestrator (brain) - makes all decisions
- Kimi K2: Default worker - fast, cheap, accurate
- Gemini 3 Flash: Large context worker - 1M tokens, 78% SWE-bench
=============================================================================
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ModelConfig:
    """Configuration for a single model"""
    model_id: str
    provider: str  # "anthropic", "openrouter", "google"
    base_url: Optional[str] = None
    pricing_prompt: float = 0.0  # per 1K tokens
    pricing_completion: float = 0.0  # per 1K tokens
    max_tokens: int = 4096
    temperature: float = 0.0
    context_limit: int = 128000  # tokens


@dataclass
class Config:
    """Main configuration for ALO v2"""

    # API Keys (loaded from environment)
    # Only 2 keys needed: Anthropic for Opus, OpenRouter for workers
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))

    # Model Configurations
    models: Dict[str, ModelConfig] = field(default_factory=lambda: {
        # ORCHESTRATOR (BRAIN)
        "opus": ModelConfig(
            model_id="claude-opus-4-5-20251101",
            provider="anthropic",
            pricing_prompt=15.0,  # $15 per 1M = $0.015 per 1K
            pricing_completion=75.0,  # $75 per 1M = $0.075 per 1K
            max_tokens=8192,
            temperature=0.0,
            context_limit=200000
        ),

        # WORKERS
        "kimi-k2": ModelConfig(
            model_id="moonshotai/kimi-k2",
            provider="openrouter",
            base_url="https://openrouter.ai/api/v1",
            pricing_prompt=0.2,  # $0.20 per 1M = $0.0002 per 1K
            pricing_completion=0.6,  # $0.60 per 1M = $0.0006 per 1K
            max_tokens=4096,
            temperature=0.0,
            context_limit=128000
        ),

        "gemini-3-flash": ModelConfig(
            model_id="google/gemini-3-flash-preview",
            provider="openrouter",
            base_url="https://openrouter.ai/api/v1",
            pricing_prompt=0.15,  # OpenRouter pricing
            pricing_completion=0.60,
            max_tokens=8192,
            temperature=0.0,
            context_limit=1000000  # 1M tokens!
        ),
    })

    # Orchestration Settings
    max_retries_per_stage: int = 2
    max_total_attempts: int = 5
    validation_timeout: int = 120  # seconds

    # Worker Selection Thresholds
    large_context_threshold: int = 100000  # tokens - use Gemini above this

    def get_model(self, name: str) -> ModelConfig:
        """Get model config by name"""
        if name not in self.models:
            raise ValueError(f"Unknown model: {name}. Available: {list(self.models.keys())}")
        return self.models[name]

    def validate(self) -> bool:
        """Validate that all required API keys are set"""
        errors = []

        if not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY not set (required for Opus orchestrator)")
        if not self.openrouter_api_key:
            errors.append("OPENROUTER_API_KEY not set (required for workers: Kimi K2, Gemini 3 Flash)")

        if errors:
            for e in errors:
                print(f"❌ {e}")
            return False

        print("✅ All API keys configured")
        return True


# Default configuration instance
default_config = Config()
