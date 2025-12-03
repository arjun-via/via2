"""
Dataclasses for the Opus Ensemble system.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class Strategy(Enum):
    """Patch generation strategies."""
    MINIMAL = "minimal"
    EXTENDED_THINKING = "extended_thinking"
    TEST_DRIVEN = "test_driven"
    REFACTOR_SAFE = "refactor_safe"
    HIGH_TEMPERATURE = "high_temperature"


@dataclass
class PatchCandidate:
    """A single patch candidate from one model instance."""
    instance_id: int
    strategy: Strategy
    code: str
    raw_response: str
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    generation_time_seconds: float = 0.0


@dataclass
class ExecutionResult:
    """Result of executing code."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    timed_out: bool = False
    execution_time_seconds: float = 0.0


@dataclass
class VerificationResult:
    """Result of verifying a patch through the 4-stage pipeline."""
    patch: PatchCandidate
    syntax_valid: bool = False
    syntax_error: Optional[str] = None
    patch_applies: bool = False
    patch_error: Optional[str] = None
    reproduction_passes: bool = False
    reproduction_output: Optional[str] = None
    regression_passes: bool = False
    regression_output: Optional[str] = None
    tests_passed: int = 0
    tests_total: int = 0

    @property
    def passed_all(self) -> bool:
        """Did this patch pass all verification stages?"""
        return (
            self.syntax_valid and
            self.patch_applies and
            self.reproduction_passes and
            self.regression_passes
        )

    @property
    def pass_rate(self) -> float:
        """Test pass rate (0.0 to 1.0)."""
        if self.tests_total == 0:
            return 0.0
        return self.tests_passed / self.tests_total


@dataclass
class EnsembleResult:
    """Final result from the Opus Ensemble system."""
    success: bool
    final_patch: Optional[str] = None
    final_code: Optional[str] = None

    # Metrics
    total_patches_generated: int = 0
    patches_syntax_valid: int = 0
    patches_apply_clean: int = 0
    patches_repro_pass: int = 0
    patches_regression_pass: int = 0

    # Winning patch info
    winning_strategy: Optional[Strategy] = None
    winning_instance_id: Optional[int] = None

    # Cost and time
    total_cost: float = 0.0
    total_time_seconds: float = 0.0
    generation_time_seconds: float = 0.0
    verification_time_seconds: float = 0.0

    # Self-correction
    correction_iterations: int = 0

    # All candidates for analysis
    all_verifications: List[VerificationResult] = field(default_factory=list)

    # Error info if failed
    error_message: Optional[str] = None
