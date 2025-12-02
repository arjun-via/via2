"""
Opus Meta-Orchestrator Package.

Provides dynamic model selection via Claude Opus 4.5 strategic planning.
Implements Anthropic's agent harness patterns:
- Feature-by-feature execution
- Clean state invariant
- Progress checkpointing
- Provider diversification
"""

from .model_registry import (
    MODEL_REGISTRY,
    ModelConfig,
    Provider,
    get_model,
    get_models_by_capability,
    get_fastest_model,
    get_cheapest_model,
)
from .feature_list import Feature, FeatureList, FeatureStatus
from .multi_provider_client import MultiProviderClient, CompletionResult
from .strategic_planner import StrategicPlanner, ExecutionPlan
from .adaptive_validator import AdaptiveValidator, ValidationResult
from .meta_orchestrator import OpusMetaOrchestrator, OrchestrationResult
from .baseline_runner import OpusBaselineRunner
from .presets import PRESETS, VariantPreset, get_preset
from .code_executor import CodeExecutor, ExecutionResult
from .prompt_evolver import PromptEvolver, ChallengeResult, Lesson, CHALLENGE_BANK
from .compounding_learner import CompoundingLearner, Pattern, AntiPattern, Convention
from .model_selection_learner import ModelSelectionLearner, TaskProfile, ModelPerformance

__all__ = [
    # Model Registry
    "MODEL_REGISTRY",
    "ModelConfig",
    "Provider",
    "get_model",
    "get_models_by_capability",
    "get_fastest_model",
    "get_cheapest_model",
    # Feature List
    "Feature",
    "FeatureList",
    "FeatureStatus",
    # Clients
    "MultiProviderClient",
    "CompletionResult",
    # Planning
    "StrategicPlanner",
    "ExecutionPlan",
    # Validation
    "AdaptiveValidator",
    "ValidationResult",
    # Orchestration
    "OpusMetaOrchestrator",
    "OrchestrationResult",
    "OpusBaselineRunner",
    # Presets
    "PRESETS",
    "VariantPreset",
    "get_preset",
    # Code Execution
    "CodeExecutor",
    "ExecutionResult",
    # Prompt Evolution
    "PromptEvolver",
    "ChallengeResult",
    "Lesson",
    "CHALLENGE_BANK",
    # Compounding Learning
    "CompoundingLearner",
    "Pattern",
    "AntiPattern",
    "Convention",
    # Model Selection Learning
    "ModelSelectionLearner",
    "TaskProfile",
    "ModelPerformance",
]
