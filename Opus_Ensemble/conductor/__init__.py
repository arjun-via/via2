"""
=============================================================================
Opus-Conductor: Multi-Agent Orchestration with Continuous Validation
=============================================================================

A next-generation orchestration system where Opus stays in the loop at every
stage, validating outputs and ensuring nothing falls through the cracks.

Key Differentiators:
- Opus validates after EVERY stage (not just plans then disappears)
- Structured handoffs with explicit acknowledgments
- Multi-layer validation (static → semantic → review → execution)
- Typed failure classification with per-type recovery strategies
- Circuit breaker to prevent infinite loops

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

from .state import (
    StageStatus,
    TaskArchetype,
    Complexity,
    ValidationCheckpoint,
    AuditEvent,
    ConductorState,
)

from .clients import (
    ModelConfig,
    ModelResponse,
    CostTracker,
    ResilientModelClient,
    ModelClientFactory,
    ProviderError,
    RateLimitError,
    AuthenticationError,
)

from .validation import (
    ValidationDecision,
    ValidationResult,
    ValidationIssue,
    StaticAnalyzer,
    SemanticValidator,
    ExecutionValidator,
    CompositeValidator,
)

from .handoff import (
    StageHandoff,
    HandoffProtocol,
    ContextAgent,
    EngineeringAgent,
    ReviewAgent,
)

from .conductor import (
    OpusConductor,
    ConductorResult,
    CircuitBreaker,
)

__all__ = [
    # State
    "StageStatus",
    "TaskArchetype",
    "Complexity",
    "ValidationCheckpoint",
    "AuditEvent",
    "ConductorState",
    # Clients
    "ModelConfig",
    "ModelResponse",
    "CostTracker",
    "ResilientModelClient",
    "ModelClientFactory",
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    # Validation
    "ValidationDecision",
    "ValidationResult",
    "ValidationIssue",
    "StaticAnalyzer",
    "SemanticValidator",
    "ExecutionValidator",
    "CompositeValidator",
    # Handoff
    "StageHandoff",
    "HandoffProtocol",
    "ContextAgent",
    "EngineeringAgent",
    "ReviewAgent",
    # Conductor
    "OpusConductor",
    "ConductorResult",
    "CircuitBreaker",
]

__version__ = "1.0.0"
