"""
=============================================================================
Opus Ensemble - Parallel Generation + Execution Filtering
=============================================================================

Beat Opus 4.5's 80.9% on SWE-bench Verified through:
1. Massive parallel generation (20-40 instances)
2. Execution-based filtering (syntax → apply → repro → regression)
3. Best patch selection

VERSION: 1.0
LAST UPDATED: 2025-12-02

USAGE:
    from Opus_Ensemble import OpusEnsemble, ModelMode

    # Production mode (Opus)
    ensemble = OpusEnsemble(mode=ModelMode.PRODUCTION)
    result = ensemble.run(issue="Fix the bug", code="...", test_code="...")

    # Testing mode (gpt-oss-120b via OpenRouter/Cerebras)
    ensemble = OpusEnsemble(mode=ModelMode.TEST)
    result = ensemble.run(issue="Fix the bug", code="...", test_code="...")

=============================================================================
"""

# Config
from .config import (
    ModelMode,
    ModelConfig,
    EnsembleConfig,
    get_config,
    get_test_config,
    STRATEGY_SYSTEM_PROMPTS,
    PATCH_GENERATION_TEMPLATE,
)

# Data types
from .data_types import (
    Strategy,
    PatchCandidate,
    ExecutionResult,
    VerificationResult,
    EnsembleResult,
)

# API client
from .api_client import (
    CompletionResult,
    EnsembleAPIClient,
    get_client,
)

# Parallel generator
from .parallel_generator import (
    ParallelGenerator,
    generate_patches,
)

# Verification
from .verification import (
    CodeExecutor,
    Verifier,
    verify_patches,
)

# Main orchestrator
from .orchestrator import (
    OpusEnsemble,
    run_ensemble,
)

__all__ = [
    # Config
    "ModelMode",
    "ModelConfig",
    "EnsembleConfig",
    "get_config",
    "get_test_config",
    "STRATEGY_SYSTEM_PROMPTS",
    "PATCH_GENERATION_TEMPLATE",
    # Data types
    "Strategy",
    "PatchCandidate",
    "ExecutionResult",
    "VerificationResult",
    "EnsembleResult",
    # API client
    "CompletionResult",
    "EnsembleAPIClient",
    "get_client",
    # Parallel generator
    "ParallelGenerator",
    "generate_patches",
    # Verification
    "CodeExecutor",
    "Verifier",
    "verify_patches",
    # Orchestrator
    "OpusEnsemble",
    "run_ensemble",
]

__version__ = "1.0.0"
