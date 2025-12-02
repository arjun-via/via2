"""
=============================================================================
SCRIPT NAME: model_registry.py
=============================================================================

Model Registry for Opus Meta-Orchestrator.
Provides unified access to all available models across providers.

INPUT FILES:
- Environment variables for API keys

OUTPUT FILES:
- None (in-memory registry)

VERSION: 1.0
LAST UPDATED: 2025-11-26

DESCRIPTION:
Central registry of all available LLM models with their configurations,
capabilities, and pricing. Supports dynamic model selection by the
Opus Meta-Orchestrator based on task requirements.

DEPENDENCIES:
- os (standard library)

=============================================================================
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import os


class Provider(Enum):
    """Supported LLM providers."""
    CEREBRAS = "cerebras"
    GROQ = "groq"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    GOOGLE_NATIVE = "google_native"  # Direct Google Gemini API


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    id: str
    provider: Provider
    base_url: str
    speed_tok_s: float
    input_price_per_m: float
    output_price_per_m: float
    context_window: int
    capabilities: List[str]

    def get_api_key(self) -> str:
        """Get API key from environment."""
        env_map = {
            Provider.CEREBRAS: "CEREBRAS_API_KEY",
            Provider.GROQ: "GROQ_API_KEY",
            Provider.OPENAI: "OPENAI_API_KEY",
            Provider.OPENROUTER: "OPENROUTER_API_KEY",
            Provider.GOOGLE_NATIVE: "GEMINI_API_KEY",
        }
        key = os.getenv(env_map[self.provider])
        if not key:
            raise ValueError(f"Missing API key: {env_map[self.provider]}")
        return key


# =============================================================================
# MODEL REGISTRY - All Available Models
# =============================================================================
# Speed data from actual tests (November 2025)
# Pricing in USD per 1M tokens

MODEL_REGISTRY: Dict[str, ModelConfig] = {
    # -------------------------------------------------------------------------
    # Cerebras Native (Fastest)
    # -------------------------------------------------------------------------
    "glm-4.6": ModelConfig(
        id="zai-glm-4.6",
        provider=Provider.CEREBRAS,
        base_url="https://api.cerebras.ai/v1",
        speed_tok_s=600,
        input_price_per_m=0.60,
        output_price_per_m=2.00,
        context_window=128000,
        capabilities=["code", "context", "fast"],
    ),
    "qwen3-235b": ModelConfig(
        id="qwen-3-235b-a22b-instruct-2507",
        provider=Provider.CEREBRAS,
        base_url="https://api.cerebras.ai/v1",
        speed_tok_s=735,
        input_price_per_m=0.60,
        output_price_per_m=1.20,
        context_window=262000,
        capabilities=["code", "reasoning", "fast"],
    ),
    "qwen3-coder": ModelConfig(
        id="qwen/qwen3-coder",
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        speed_tok_s=178,
        input_price_per_m=0.20,
        output_price_per_m=0.60,
        context_window=262000,
        capabilities=["code", "engineering", "swe-bench"],
    ),

    # -------------------------------------------------------------------------
    # Kimi K2 via OpenRouter (Groq key expired)
    # -------------------------------------------------------------------------
    "kimi-k2": ModelConfig(
        id="moonshotai/kimi-k2",
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        speed_tok_s=200,
        input_price_per_m=0.14,
        output_price_per_m=0.28,
        context_window=131000,
        capabilities=["code", "review", "agentic", "fast"],
    ),

    # -------------------------------------------------------------------------
    # OpenAI Native (ZDR Compliance)
    # -------------------------------------------------------------------------
    "gpt-5.1": ModelConfig(
        id="gpt-5.1",
        provider=Provider.OPENAI,
        base_url="https://api.openai.com/v1",
        speed_tok_s=72,
        input_price_per_m=1.25,
        output_price_per_m=10.00,
        context_window=272000,
        capabilities=["code", "reasoning", "premium"],
    ),

    # -------------------------------------------------------------------------
    # OpenRouter (Premium Models)
    # -------------------------------------------------------------------------
    "opus-4.5": ModelConfig(
        id="anthropic/claude-opus-4",
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        speed_tok_s=45,
        input_price_per_m=5.00,
        output_price_per_m=25.00,
        context_window=200000,
        capabilities=["code", "reasoning", "architecture", "premium"],
    ),
    "sonnet-4.5": ModelConfig(
        id="anthropic/claude-sonnet-4",
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        speed_tok_s=77,
        input_price_per_m=3.00,
        output_price_per_m=15.00,
        context_window=200000,
        capabilities=["code", "reasoning", "review", "premium"],
    ),
    "gemini-3-pro": ModelConfig(
        id="google/gemini-3-pro-preview",
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        speed_tok_s=80,
        input_price_per_m=1.50,
        output_price_per_m=12.00,
        context_window=1000000,
        capabilities=["context", "reasoning", "large-context", "code", "premium"],
    ),
    "gemini-2.5-flash": ModelConfig(
        id="google/gemini-2.5-flash",
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        speed_tok_s=200,
        input_price_per_m=0.15,
        output_price_per_m=0.60,
        context_window=1000000,
        capabilities=["context", "fast", "large-context", "code"],
    ),

    # -------------------------------------------------------------------------
    # Google Native (Direct Gemini API - requires google-genai SDK)
    # NOTE: Gemini 3 Pro preview has unstable thinking mode via native API
    # Use OpenRouter version above for stability
    # -------------------------------------------------------------------------
    "gemini-2.0-flash-native": ModelConfig(
        id="gemini-2.0-flash-exp",  # Native Google model ID (stable, no thinking mode)
        provider=Provider.GOOGLE_NATIVE,
        base_url="https://generativelanguage.googleapis.com",  # Not used directly
        speed_tok_s=200,
        input_price_per_m=0.10,
        output_price_per_m=0.40,
        context_window=1000000,  # 1M context window
        capabilities=["context", "fast", "large-context", "code"],
    ),
    "kimi-k2-thinking": ModelConfig(
        id="moonshotai/kimi-k2-thinking",
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        speed_tok_s=31,
        input_price_per_m=1.00,
        output_price_per_m=3.00,
        context_window=131000,
        capabilities=["reasoning", "review", "deep-analysis"],
    ),
}


def get_model(name: str) -> ModelConfig:
    """
    Get model config by name.

    Args:
        name: Model name (e.g., "glm-4.6", "opus-4.5")

    Returns:
        ModelConfig for the requested model

    Raises:
        ValueError: If model name not found in registry
    """
    if name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {name}. Available: {list(MODEL_REGISTRY.keys())}")
    return MODEL_REGISTRY[name]


def get_models_by_capability(capability: str) -> List[ModelConfig]:
    """
    Get all models with a specific capability.

    Args:
        capability: Capability to filter by (e.g., "code", "fast", "premium")

    Returns:
        List of ModelConfig objects with the specified capability
    """
    return [m for m in MODEL_REGISTRY.values() if capability in m.capabilities]


def get_fastest_model(capability: Optional[str] = None) -> ModelConfig:
    """
    Get the fastest model, optionally filtered by capability.

    Args:
        capability: Optional capability filter

    Returns:
        ModelConfig for the fastest matching model
    """
    models = list(MODEL_REGISTRY.values())
    if capability:
        models = [m for m in models if capability in m.capabilities]
    if not models:
        raise ValueError(f"No models found with capability: {capability}")
    return max(models, key=lambda m: m.speed_tok_s)


def get_cheapest_model(capability: Optional[str] = None) -> ModelConfig:
    """
    Get the cheapest model, optionally filtered by capability.

    Args:
        capability: Optional capability filter

    Returns:
        ModelConfig for the cheapest matching model
    """
    models = list(MODEL_REGISTRY.values())
    if capability:
        models = [m for m in models if capability in m.capabilities]
    if not models:
        raise ValueError(f"No models found with capability: {capability}")
    return min(models, key=lambda m: m.output_price_per_m)


def get_model_menu() -> str:
    """
    Format model registry as a menu string for prompts.

    Returns:
        Formatted string listing all models with capabilities
    """
    lines = []
    for name, config in MODEL_REGISTRY.items():
        lines.append(
            f"- {name}: {config.speed_tok_s} tok/s, "
            f"${config.output_price_per_m}/M output, "
            f"capabilities: {', '.join(config.capabilities)}"
        )
    return "\n".join(lines)
