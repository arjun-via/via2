"""
=============================================================================
SCRIPT NAME: presets.py
=============================================================================

Variant Presets - Constrain which models Opus can select.

INPUT FILES:
- None (configuration)

OUTPUT FILES:
- None (in-memory)

VERSION: 1.0
LAST UPDATED: 2025-11-26

DESCRIPTION:
Defines preset configurations for different Opus Meta-Orchestrator variants.
Each preset constrains which models can be selected and provides defaults.

DEPENDENCIES:
- None (standard library only)

=============================================================================
"""

from typing import List, Dict
from dataclasses import dataclass


@dataclass
class VariantPreset:
    """
    Preset that constrains model selection.

    Attributes:
        name: Human-readable name
        description: What this preset optimizes for
        allowed_models: List of model names Opus can choose from
        default_context: Default model for context gathering
        default_engineering: Default model for code generation
        default_review: Default model for code review
        upgrade_path: Model upgrade sequence when retries needed
    """
    name: str
    description: str
    allowed_models: List[str]
    default_context: str
    default_engineering: str
    default_review: str
    upgrade_path: Dict[str, str] = None

    def __post_init__(self):
        if self.upgrade_path is None:
            self.upgrade_path = {}


# =============================================================================
# VARIANT PRESETS
# =============================================================================

PRESETS = {
    # -------------------------------------------------------------------------
    # Opus-Open: Fast OSS models via native APIs
    # -------------------------------------------------------------------------
    "opus-open": VariantPreset(
        name="Opus-Open",
        description="Fast open-source models via native APIs (Cerebras, Groq)",
        allowed_models=["glm-4.6", "qwen3-235b", "kimi-k2", "kimi-k2-thinking"],
        default_context="glm-4.6",
        default_engineering="qwen3-235b",
        default_review="kimi-k2",
        upgrade_path={
            "qwen3-235b": "kimi-k2-thinking",  # Stay within open models
            "glm-4.6": "qwen3-235b",
        }
    ),

    # -------------------------------------------------------------------------
    # Opus-Optimized: Best cost/quality balance
    # -------------------------------------------------------------------------
    "opus-optimized": VariantPreset(
        name="Opus-Optimized",
        description="Best cost/quality balance with provider diversification",
        allowed_models=[
            "gemini-2.5-flash", "qwen3-235b", "qwen3-coder", "kimi-k2", "kimi-k2-thinking", "gpt-5.1"
        ],
        default_context="gemini-2.5-flash",  # 1M context via OpenRouter (stable)
        default_engineering="qwen3-235b",    # 30x faster, better patch rate than qwen3-coder
        default_review="kimi-k2",
        upgrade_path={
            "qwen3-235b": "gpt-5.1",
            "gpt-5.1": "sonnet-4.5",
        }
    ),

    # -------------------------------------------------------------------------
    # Opus-BestInClass: Maximum quality
    # -------------------------------------------------------------------------
    "opus-bestinclass": VariantPreset(
        name="Opus-BestInClass",
        description="Maximum quality with premium models",
        allowed_models=[
            "gemini-2.5-flash", "gpt-5.1", "sonnet-4.5",
            "opus-4.5", "kimi-k2-thinking"
        ],
        default_context="gemini-2.5-flash",  # 1M context via OpenRouter (stable)
        default_engineering="gpt-5.1",
        default_review="sonnet-4.5",
        upgrade_path={
            "gpt-5.1": "sonnet-4.5",
            "sonnet-4.5": "opus-4.5",
        }
    ),

    # -------------------------------------------------------------------------
    # Opus-Full: Full Opus stack
    # -------------------------------------------------------------------------
    "opus-full": VariantPreset(
        name="Opus-Full",
        description="Full Opus stack for maximum intelligence",
        allowed_models=["opus-4.5"],
        default_context="opus-4.5",
        default_engineering="opus-4.5",
        default_review="opus-4.5",
        upgrade_path={}  # No upgrade - already at max
    ),
}


def get_preset(name: str) -> VariantPreset:
    """
    Get preset by name.

    Args:
        name: Preset name (opus-open, opus-optimized, opus-bestinclass, opus-full)

    Returns:
        VariantPreset configuration

    Raises:
        ValueError: If preset name not found
    """
    if name not in PRESETS:
        available = list(PRESETS.keys())
        raise ValueError(f"Unknown preset: {name}. Available: {available}")
    return PRESETS[name]


def list_presets() -> List[str]:
    """
    List all available preset names.

    Returns:
        List of preset names
    """
    return list(PRESETS.keys())


def describe_presets() -> str:
    """
    Get descriptions of all presets.

    Returns:
        Formatted string with all preset descriptions
    """
    lines = ["Available Opus Meta-Orchestrator Presets:", ""]
    for name, preset in PRESETS.items():
        lines.append(f"  {name}:")
        lines.append(f"    {preset.description}")
        lines.append(f"    Models: {', '.join(preset.allowed_models)}")
        lines.append("")
    return "\n".join(lines)
