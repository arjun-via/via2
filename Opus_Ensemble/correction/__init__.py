"""
Self-correction loop module for Opus Ensemble.

Iteratively refines patches based on:
- Test failure analysis
- Error message parsing
- Execution feedback

The loop:
1. Take a failing patch + error info
2. Ask LLM to fix based on error
3. Re-verify in Docker
4. Repeat until pass or max iterations
"""

from .self_correction import (
    SelfCorrectionLoop,
    CorrectionResult,
    CorrectionConfig,
)

__all__ = [
    "SelfCorrectionLoop",
    "CorrectionResult",
    "CorrectionConfig",
]
