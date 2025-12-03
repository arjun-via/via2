"""
=============================================================================
Opus-Conductor Advanced Patterns
=============================================================================

Advanced orchestration patterns for improved code generation:
1. Debate - Multi-agent debate for complex problems
2. Ensemble - Parallel generation with voting/selection
3. Learning - Prompt evolution and model selection learning

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

from .debate import DebateOrchestrator, DebateRound, DebateResult
from .ensemble import EnsembleOrchestrator, EnsembleStrategy, EnsembleResult
from .learning import PromptEvolver, ModelSelector, LearningModule

__all__ = [
    # Debate
    "DebateOrchestrator",
    "DebateRound",
    "DebateResult",
    # Ensemble
    "EnsembleOrchestrator",
    "EnsembleStrategy",
    "EnsembleResult",
    # Learning
    "PromptEvolver",
    "ModelSelector",
    "LearningModule",
]
