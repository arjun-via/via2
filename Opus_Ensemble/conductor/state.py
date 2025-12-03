"""
=============================================================================
SCRIPT NAME: state.py
=============================================================================

Opus-Conductor State Management

This module defines all data structures for the orchestration state.
The ConductorState is the single source of truth - all agents read from
and write to this shared state, ensuring nothing is lost between stages.

Key Classes:
- StageStatus: Enum for tracking stage progress
- ValidationCheckpoint: Records Opus validation decisions
- AuditEvent: Tracks every action for debugging/learning
- ConductorState: The central state object passed through all stages

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import time
import json
import uuid


class StageStatus(Enum):
    """Status of each orchestration stage."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATED = "validated"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskArchetype(Enum):
    """Classification of task types for routing strategies."""
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    TEST = "test"
    UNKNOWN = "unknown"


class Complexity(Enum):
    """Task complexity levels."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    EXPERT = "expert"


@dataclass
class ValidationCheckpoint:
    """
    Records an Opus validation decision at a stage boundary.

    Every time Opus validates an intermediate output, we create one of these
    to track what was checked and what the decision was.
    """
    stage: str                          # e.g., "context", "engineering", "review"
    timestamp: float                    # UNIX epoch seconds
    decision: str                       # "APPROVED" | "RETRY" | "ESCALATE"
    reasoning: str                      # Opus's textual explanation
    issues: List[str] = field(default_factory=list)  # Specific issues found
    guidance: Optional[str] = None      # How to fix on retry
    retry_count: int = 0                # How many retries at this checkpoint

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stage": self.stage,
            "timestamp": self.timestamp,
            "decision": self.decision,
            "reasoning": self.reasoning,
            "issues": self.issues,
            "guidance": self.guidance,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationCheckpoint":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class AuditEvent:
    """
    Records a single action in the orchestration audit trail.

    Every model call, validation, retry, and error is logged here for
    debugging and learning purposes.
    """
    timestamp: float
    event_type: str                     # "stage_start" | "stage_end" | "model_call" | "validation" | "retry" | "error"
    stage: str
    model_id: str = ""
    input_preview: str = ""             # Truncated input for debugging
    output_preview: str = ""            # Truncated output for debugging
    cost: float = 0.0
    tokens: int = 0
    duration: float = 0.0               # Seconds
    validation_result: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "stage": self.stage,
            "model_id": self.model_id,
            "input_preview": self.input_preview[:500] if self.input_preview else "",
            "output_preview": self.output_preview[:500] if self.output_preview else "",
            "cost": self.cost,
            "tokens": self.tokens,
            "duration": self.duration,
            "validation_result": self.validation_result,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class ConductorState:
    """
    The central state object for Opus-Conductor orchestration.

    This is the single source of truth that flows through all stages.
    All agents read from and write to this state. Opus validates changes
    at each checkpoint.

    Key Design Principles:
    1. Explicit over implicit - all requirements are fields, not buried in prose
    2. Verifiable - helper methods check if requirements are met
    3. Serializable - can be saved/restored for long-running tasks
    4. Auditable - full history of what happened and why
    """

    # =========================================================================
    # TASK IDENTITY & METADATA
    # =========================================================================
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    original_task: str = ""             # User's original request
    task_archetype: TaskArchetype = TaskArchetype.UNKNOWN
    complexity: Complexity = Complexity.MEDIUM
    repo_path: Optional[str] = None     # Path to target repository (for SWE-bench)

    # =========================================================================
    # GLOBAL REQUIREMENTS (from Opus planning)
    # These are the "contracts" that downstream stages must fulfill
    # =========================================================================
    constraints: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    required_imports: List[str] = field(default_factory=list)
    edge_cases: List[str] = field(default_factory=list)
    plan: str = ""                      # High-level plan text

    # =========================================================================
    # CONTEXT STAGE
    # =========================================================================
    context_status: StageStatus = StageStatus.PENDING
    relevant_files: List[str] = field(default_factory=list)
    context_summary: str = ""
    file_contents: Dict[str, str] = field(default_factory=dict)  # filename -> content
    context_validation: Optional[ValidationCheckpoint] = None

    # =========================================================================
    # ENGINEERING STAGE
    # =========================================================================
    engineering_status: StageStatus = StageStatus.PENDING
    implementation_code: str = ""
    implementation_files: Dict[str, str] = field(default_factory=dict)  # For multi-file changes
    imports_included: List[str] = field(default_factory=list)  # From static analysis
    edge_cases_handled: Dict[str, bool] = field(default_factory=dict)  # edge_case -> handled?
    engineering_validation: Optional[ValidationCheckpoint] = None
    engineering_acknowledgment: str = ""  # Agent's acknowledgment of requirements

    # =========================================================================
    # REVIEW STAGE
    # =========================================================================
    review_status: StageStatus = StageStatus.PENDING
    review_passed: bool = False
    review_issues: List[str] = field(default_factory=list)
    review_feedback: str = ""
    review_validation: Optional[ValidationCheckpoint] = None

    # =========================================================================
    # EXECUTION STAGE
    # =========================================================================
    execution_status: StageStatus = StageStatus.PENDING
    execution_passed: bool = False
    execution_output: str = ""
    execution_errors: List[str] = field(default_factory=list)
    test_results: Dict[str, bool] = field(default_factory=dict)  # test_name -> passed

    # =========================================================================
    # META / TRACKING
    # =========================================================================
    total_cost: float = 0.0
    total_tokens: int = 0
    total_time: float = 0.0
    retry_count: int = 0
    stage_retries: Dict[str, int] = field(default_factory=dict)  # stage -> retry count
    checkpoints: List[ValidationCheckpoint] = field(default_factory=list)
    audit_events: List[AuditEvent] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    # =========================================================================
    # FINAL OUTPUT
    # =========================================================================
    final_code: str = ""
    final_diff: str = ""
    success: bool = False
    failure_reason: Optional[str] = None

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def verify_imports_complete(self) -> bool:
        """
        Check if all required imports are present in the implementation.

        Returns:
            True if all required_imports appear in imports_included
        """
        if not self.required_imports:
            return True
        return all(
            any(req in included for included in self.imports_included)
            for req in self.required_imports
        )

    def get_missing_imports(self) -> List[str]:
        """Get list of required imports that are missing."""
        if not self.required_imports:
            return []
        return [
            req for req in self.required_imports
            if not any(req in included for included in self.imports_included)
        ]

    def verify_edge_cases_handled(self) -> bool:
        """
        Check if all identified edge cases are marked as handled.

        Returns:
            True if every edge_case is True in edge_cases_handled
        """
        if not self.edge_cases:
            return True
        return all(
            self.edge_cases_handled.get(edge, False)
            for edge in self.edge_cases
        )

    def get_unhandled_edge_cases(self) -> List[str]:
        """Get list of edge cases not marked as handled."""
        if not self.edge_cases:
            return []
        return [
            edge for edge in self.edge_cases
            if not self.edge_cases_handled.get(edge, False)
        ]

    def add_checkpoint(self, checkpoint: ValidationCheckpoint) -> None:
        """Add a validation checkpoint to the history."""
        self.checkpoints.append(checkpoint)

    def add_audit_event(self, event: AuditEvent) -> None:
        """Add an audit event to the history."""
        self.audit_events.append(event)

    def log_model_call(
        self,
        stage: str,
        model_id: str,
        input_text: str,
        output_text: str,
        cost: float = 0.0,
        tokens: int = 0,
        duration: float = 0.0,
    ) -> None:
        """Convenience method to log a model API call."""
        self.add_audit_event(AuditEvent(
            timestamp=time.time(),
            event_type="model_call",
            stage=stage,
            model_id=model_id,
            input_preview=input_text[:500] if input_text else "",
            output_preview=output_text[:500] if output_text else "",
            cost=cost,
            tokens=tokens,
            duration=duration,
        ))
        self.total_cost += cost
        self.total_tokens += tokens

    def log_error(self, stage: str, error_message: str, metadata: Dict[str, Any] = None) -> None:
        """Log an error event."""
        self.add_audit_event(AuditEvent(
            timestamp=time.time(),
            event_type="error",
            stage=stage,
            error_message=error_message,
            metadata=metadata or {},
        ))

    def increment_retry(self, stage: str) -> int:
        """Increment retry count for a stage and return new count."""
        self.stage_retries[stage] = self.stage_retries.get(stage, 0) + 1
        self.retry_count += 1
        return self.stage_retries[stage]

    def get_stage_retry_count(self, stage: str) -> int:
        """Get retry count for a specific stage."""
        return self.stage_retries.get(stage, 0)

    def get_elapsed_time(self) -> float:
        """Get elapsed time since start."""
        return time.time() - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for JSON serialization."""
        return {
            # Task identity
            "task_id": self.task_id,
            "original_task": self.original_task,
            "task_archetype": self.task_archetype.value,
            "complexity": self.complexity.value,
            "repo_path": self.repo_path,

            # Requirements
            "constraints": self.constraints,
            "success_criteria": self.success_criteria,
            "required_imports": self.required_imports,
            "edge_cases": self.edge_cases,
            "plan": self.plan,

            # Context
            "context_status": self.context_status.value,
            "relevant_files": self.relevant_files,
            "context_summary": self.context_summary,
            "context_validation": self.context_validation.to_dict() if self.context_validation else None,

            # Engineering
            "engineering_status": self.engineering_status.value,
            "implementation_code": self.implementation_code,
            "imports_included": self.imports_included,
            "edge_cases_handled": self.edge_cases_handled,
            "engineering_validation": self.engineering_validation.to_dict() if self.engineering_validation else None,

            # Review
            "review_status": self.review_status.value,
            "review_passed": self.review_passed,
            "review_issues": self.review_issues,
            "review_validation": self.review_validation.to_dict() if self.review_validation else None,

            # Execution
            "execution_status": self.execution_status.value,
            "execution_passed": self.execution_passed,
            "execution_output": self.execution_output,
            "execution_errors": self.execution_errors,

            # Meta
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens,
            "total_time": self.get_elapsed_time(),
            "retry_count": self.retry_count,
            "stage_retries": self.stage_retries,
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],

            # Output
            "final_code": self.final_code,
            "success": self.success,
            "failure_reason": self.failure_reason,
        }

    def save(self, filepath: str) -> None:
        """Save state to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "ConductorState":
        """Load state from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        state = cls()
        state.task_id = data.get("task_id", state.task_id)
        state.original_task = data.get("original_task", "")
        state.task_archetype = TaskArchetype(data.get("task_archetype", "unknown"))
        state.complexity = Complexity(data.get("complexity", "medium"))
        state.repo_path = data.get("repo_path")

        state.constraints = data.get("constraints", [])
        state.success_criteria = data.get("success_criteria", [])
        state.required_imports = data.get("required_imports", [])
        state.edge_cases = data.get("edge_cases", [])
        state.plan = data.get("plan", "")

        state.context_status = StageStatus(data.get("context_status", "pending"))
        state.relevant_files = data.get("relevant_files", [])
        state.context_summary = data.get("context_summary", "")

        state.engineering_status = StageStatus(data.get("engineering_status", "pending"))
        state.implementation_code = data.get("implementation_code", "")
        state.imports_included = data.get("imports_included", [])
        state.edge_cases_handled = data.get("edge_cases_handled", {})

        state.review_status = StageStatus(data.get("review_status", "pending"))
        state.review_passed = data.get("review_passed", False)
        state.review_issues = data.get("review_issues", [])

        state.execution_status = StageStatus(data.get("execution_status", "pending"))
        state.execution_passed = data.get("execution_passed", False)
        state.execution_output = data.get("execution_output", "")
        state.execution_errors = data.get("execution_errors", [])

        state.total_cost = data.get("total_cost", 0.0)
        state.total_tokens = data.get("total_tokens", 0)
        state.retry_count = data.get("retry_count", 0)
        state.stage_retries = data.get("stage_retries", {})

        state.final_code = data.get("final_code", "")
        state.success = data.get("success", False)
        state.failure_reason = data.get("failure_reason")

        # Load checkpoints
        for cp_data in data.get("checkpoints", []):
            state.checkpoints.append(ValidationCheckpoint.from_dict(cp_data))

        return state

    def get_summary(self) -> str:
        """Get a human-readable summary of current state."""
        lines = [
            f"Task: {self.task_id}",
            f"Status: {'SUCCESS' if self.success else 'IN PROGRESS' if not self.failure_reason else 'FAILED'}",
            f"Archetype: {self.task_archetype.value}",
            f"Complexity: {self.complexity.value}",
            "",
            "Stage Status:",
            f"  Context: {self.context_status.value}",
            f"  Engineering: {self.engineering_status.value}",
            f"  Review: {self.review_status.value}",
            f"  Execution: {self.execution_status.value}",
            "",
            f"Requirements:",
            f"  Imports: {len(self.required_imports)} required, {len(self.imports_included)} found",
            f"  Edge cases: {len(self.edge_cases)} identified, {sum(self.edge_cases_handled.values())} handled",
            "",
            f"Metrics:",
            f"  Cost: ${self.total_cost:.4f}",
            f"  Tokens: {self.total_tokens:,}",
            f"  Time: {self.get_elapsed_time():.1f}s",
            f"  Retries: {self.retry_count}",
        ]

        if self.failure_reason:
            lines.append(f"\nFailure: {self.failure_reason}")

        return "\n".join(lines)
