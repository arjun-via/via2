"""
=============================================================================
SCRIPT NAME: config.py
=============================================================================

Configuration for the Opus Ensemble system.

Supports multiple model modes:
- Production: Claude Opus 4.5 (highest quality, highest cost)
- Testing: GPT-4.1-mini via OpenRouter/Cerebras (fast, cheap)
- Budget: Qwen 235B (medium cost/quality)

VERSION: 1.0
LAST UPDATED: 2025-12-02

USAGE:
    from config import get_config, ModelMode

    # Use testing mode
    config = get_config(ModelMode.TEST)

    # Or via environment variable
    # export OPUS_ENSEMBLE_MODEL=test
    config = get_config()

=============================================================================
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class ModelMode(Enum):
    """Model mode selection."""
    PRODUCTION = "opus"      # Claude Opus 4.5 - highest quality
    TEST = "test"            # GPT-OSS-120B via OpenRouter/Cerebras - fast & free


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    model_id: str
    provider: str
    base_url: str
    api_key_env: str
    input_price_per_m: float
    output_price_per_m: float
    max_tokens: int = 8192
    temperature: float = 0.0
    supports_extended_thinking: bool = False

    @property
    def api_key(self) -> str:
        """Get API key from environment."""
        key = os.environ.get(self.api_key_env)
        if not key:
            raise ValueError(f"Missing API key: {self.api_key_env}")
        return key


# =============================================================================
# MODEL DEFINITIONS
# =============================================================================

MODELS = {
    # Production: Claude Opus 4.5
    ModelMode.PRODUCTION: ModelConfig(
        model_id="claude-opus-4-5-20251101",
        provider="anthropic",
        base_url="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
        input_price_per_m=5.0,
        output_price_per_m=25.0,
        max_tokens=16384,
        temperature=0.0,
        supports_extended_thinking=True,
    ),

    # Testing: GPT-OSS-120B via OpenRouter (Cerebras provider)
    ModelMode.TEST: ModelConfig(
        model_id="openai/gpt-oss-120b",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        input_price_per_m=0.35,  # $0.35 per M input tokens
        output_price_per_m=0.75,  # $0.75 per M output tokens
        max_tokens=8192,
        temperature=0.0,
        supports_extended_thinking=False,
    ),
}


@dataclass
class EnsembleConfig:
    """Full configuration for the Opus Ensemble system."""

    # Model configuration
    mode: ModelMode = ModelMode.PRODUCTION
    model: ModelConfig = field(default=None)

    # Parallel generation settings
    num_parallel_instances: int = 40
    strategy_distribution: Dict[str, int] = field(default_factory=lambda: {
        "minimal": 8,
        "extended_thinking": 8,
        "test_driven": 8,
        "refactor_safe": 8,
        "high_temperature": 8,
    })

    # Temperature overrides per strategy
    strategy_temperatures: Dict[str, float] = field(default_factory=lambda: {
        "minimal": 0.0,
        "extended_thinking": 0.0,
        "test_driven": 0.0,
        "refactor_safe": 0.0,
        "high_temperature": 0.8,
    })

    # Localization settings
    localization_top_k: int = 5  # Top files per strategy
    localization_strategies: List[str] = field(default_factory=lambda: [
        "ast_search",
        "dense_sparse",
        "knowledge_graph",
    ])

    # Verification settings
    syntax_check_enabled: bool = True
    regression_test_enabled: bool = True
    reproduction_test_enabled: bool = True

    # Self-correction settings
    max_correction_iterations: int = 3

    # Docker settings
    docker_timeout_seconds: int = 60
    docker_memory_limit: str = "4g"
    docker_cpu_limit: float = 2.0

    # Retry settings
    api_max_retries: int = 3
    api_retry_delay_seconds: float = 1.0
    api_retry_backoff: float = 2.0

    # Logging
    log_level: str = "INFO"
    trace_to_jsonl: bool = True
    trace_file: str = "ensemble_trace.jsonl"

    def __post_init__(self):
        """Initialize model config based on mode."""
        if self.model is None:
            self.model = MODELS[self.mode]


def get_config(mode: Optional[ModelMode] = None) -> EnsembleConfig:
    """
    Get configuration, optionally overriding mode.

    Priority:
    1. Explicit mode parameter
    2. OPUS_ENSEMBLE_MODEL environment variable
    3. Default to PRODUCTION

    Args:
        mode: Optional explicit mode override

    Returns:
        EnsembleConfig with all settings
    """
    if mode is None:
        env_mode = os.environ.get("OPUS_ENSEMBLE_MODEL", "opus").lower()
        mode_map = {
            "opus": ModelMode.PRODUCTION,
            "production": ModelMode.PRODUCTION,
            "test": ModelMode.TEST,
            "testing": ModelMode.TEST,
        }
        mode = mode_map.get(env_mode, ModelMode.PRODUCTION)

    return EnsembleConfig(mode=mode)


def get_test_config() -> EnsembleConfig:
    """
    Get configuration optimized for testing (fast, cheap).

    Uses fewer parallel instances and the cheap test model.
    """
    config = get_config(ModelMode.TEST)
    config.num_parallel_instances = 5  # Reduce for testing
    config.strategy_distribution = {
        "minimal": 2,
        "extended_thinking": 1,
        "test_driven": 1,
        "refactor_safe": 1,
        "high_temperature": 0,
    }
    config.max_correction_iterations = 1
    return config


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

STRATEGY_SYSTEM_PROMPTS = {
    "minimal": """You are an expert software engineer. Your goal is to produce the SMALLEST possible patch that fixes the bug.

Rules:
- Make the minimum number of line changes
- Do not refactor or improve code style
- Do not add extra features or edge case handling beyond what's needed
- Focus only on the specific bug described
- Prefer simple, direct fixes over elegant ones""",

    "extended_thinking": """You are an expert software engineer. Take your time to deeply analyze this problem before writing code.

Process:
1. First, understand the bug completely - trace through the code mentally
2. Consider multiple possible root causes
3. Think about edge cases that might be related
4. Only then, write your fix

Show your reasoning step by step before providing the patch.""",

    "test_driven": """You are an expert software engineer using test-driven development.

Process:
1. First, understand what test would demonstrate the bug is fixed
2. Consider what edge cases the fix should handle
3. Write the fix that would make those tests pass
4. Ensure backwards compatibility with existing tests

Think about testing implications throughout.""",

    "refactor_safe": """You are an expert software engineer focused on safe, maintainable fixes.

Rules:
- Preserve existing code patterns and style
- Maintain backwards compatibility
- Don't break any existing interfaces
- Consider how this code is used elsewhere
- Add defensive checks if appropriate
- Prefer explicit over implicit behavior""",

    "high_temperature": """You are an expert software engineer exploring creative solutions.

Be creative and consider unconventional approaches:
- What if the bug is actually a symptom of a deeper issue?
- Are there alternative algorithms that would work better?
- Consider edge cases others might miss
- Think about corner cases in the original implementation

Provide a working fix, but don't be afraid to think outside the box.""",
}


PATCH_GENERATION_TEMPLATE = """You are fixing a bug in a Python codebase.

## Issue Description
{issue}

## Relevant Code (including TEST FILES that must pass)
{code}

## Additional Test Info
{reproduction_test}

## CRITICAL INSTRUCTIONS
1. **READ THE TEST FILES CAREFULLY** - The "TEST FILE (must pass)" sections show exactly what behavior is expected
2. Study what the tests are checking - understand what inputs produce what expected outputs
3. Trace through the source code to find the bug
4. Write a minimal fix that makes the tests pass

## Output Format
Return ONLY the changes using this EXACT format:
```
<<<<<<< SEARCH
path/to/file.py
=======
EXACT lines to find (copy exactly from the code shown above)
=======
REPLACEMENT lines (your fixed code)
>>>>>>> REPLACE
```

IMPORTANT:
- The SEARCH section must contain EXACT text from the file (copy-paste from above)
- Include 2-3 lines of context before and after the change
- You can include multiple SEARCH/REPLACE blocks for multiple changes
- Do NOT include line numbers in the search text
- ONLY modify source files, NOT test files

Example:
```
<<<<<<< SEARCH
astropy/modeling/separable.py
=======
def separability_matrix(transform):
    if isinstance(transform, CompoundModel):
        sepleft = separability_matrix(transform.left)
=======
def separability_matrix(transform):
    if isinstance(transform, CompoundModel):
        # Fixed: handle nested compound models
        sepleft = separability_matrix(transform.left)
>>>>>>> REPLACE
```
"""


REPRODUCTION_TEST_TEMPLATE = """You are writing a test that demonstrates a bug exists.

## Issue Description
{issue}

## Relevant Code
{code}

## Instructions
Write a minimal test case that:
1. FAILS on the current (buggy) code
2. Would PASS if the bug were fixed
3. Tests exactly the behavior described in the issue

The test should be self-contained and runnable with pytest.

## Output Format
```python
def test_reproduction():
    # Your test code here
    # This should FAIL currently, demonstrating the bug exists
    ...
```
"""


SELF_CORRECTION_TEMPLATE = """Your previous patch attempt failed. Analyze the failure and try again.

## Issue Description
{issue}

## Relevant Code
{code}

## Your Previous Patch
```diff
{previous_patch}
```

## Failure Information
{failure_info}

## Instructions
1. Analyze why your previous patch failed
2. Understand the error message/test failure
3. Write a corrected patch that addresses the issue

Do NOT repeat the same mistake. Learn from the failure.

## Output Format
Return ONLY the unified diff patch.
"""


if __name__ == "__main__":
    # Test configuration
    print("=" * 60)
    print("OPUS ENSEMBLE CONFIGURATION TEST")
    print("=" * 60)

    for mode in ModelMode:
        config = get_config(mode)
        print(f"\n{mode.name} mode:")
        print(f"  Model: {config.model.model_id}")
        print(f"  Provider: {config.model.provider}")
        print(f"  Cost: ${config.model.input_price_per_m}/${config.model.output_price_per_m} per M tokens")
        print(f"  Parallel instances: {config.num_parallel_instances}")

    print("\n" + "=" * 60)
    print("Test config (reduced for development):")
    test_config = get_test_config()
    print(f"  Model: {test_config.model.model_id}")
    print(f"  Parallel instances: {test_config.num_parallel_instances}")
    print(f"  Strategies: {test_config.strategy_distribution}")
