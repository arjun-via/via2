"""
Reproduction test generation module for Opus Ensemble.

Generates failing tests that prove the bug exists:
- Analyze issue description + localized code
- Generate test code using LLM
- Execute against base commit to verify it FAILS
- Retry if test passes (didn't capture bug)
"""

from .test_generator import (
    ReproductionGenerator,
    ReproductionResult,
    ReproductionConfig,
)

__all__ = [
    "ReproductionGenerator",
    "ReproductionResult",
    "ReproductionConfig",
]
