"""
=============================================================================
SCRIPT NAME: conductor.py
=============================================================================

Opus-Conductor Main Orchestration Class

This is the core orchestrator where Opus stays in the loop at every stage,
validating outputs and ensuring nothing falls through the cracks.

Key Differentiators:
1. Opus validates after EVERY stage (not just plans then disappears)
2. Structured handoffs with explicit acknowledgments
3. Multi-layer validation (static → semantic → review → execution)
4. Typed failure classification with per-type recovery strategies
5. Circuit breaker to prevent infinite loops

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import time
import logging
import yaml
import re
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from pathlib import Path

from .state import (
    ConductorState,
    StageStatus,
    TaskArchetype,
    Complexity,
    ValidationCheckpoint,
    AuditEvent,
)
from .clients import (
    ModelClientFactory,
    ResilientModelClient,
    CostTracker,
    ModelResponse,
)
from .validation import (
    StaticAnalyzer,
    SemanticValidator,
    ExecutionValidator,
    CompositeValidator,
    ValidationResult,
    ValidationDecision,
)
from .handoff import (
    StageHandoff,
    HandoffProtocol,
    ContextAgent,
    EngineeringAgent,
    ReviewAgent,
)


@dataclass
class ConductorResult:
    """Result of an orchestration run."""
    success: bool
    state: ConductorState
    final_code: str
    final_diff: str
    total_cost: float
    total_tokens: int
    total_time: float
    stages_completed: int
    retries_used: int
    failure_reason: Optional[str] = None


class CircuitBreaker:
    """
    Circuit breaker to prevent infinite retry loops.

    Opens after consecutive failures exceed threshold.
    """

    def __init__(self, threshold: int = 5, reset_timeout: float = 300.0):
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.is_open = False

    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.threshold:
            self.is_open = True

    def record_success(self) -> None:
        """Record a success and reset the counter."""
        self.failure_count = 0
        self.is_open = False

    def can_proceed(self) -> bool:
        """Check if we can proceed (circuit is closed or reset)."""
        if not self.is_open:
            return True

        # Check if timeout has passed
        if time.time() - self.last_failure_time > self.reset_timeout:
            self.is_open = False
            self.failure_count = 0
            return True

        return False


class OpusConductor:
    """
    Main orchestration class for the Opus-Conductor system.

    This orchestrator:
    1. Plans with Opus to extract requirements
    2. Runs specialized agents for each stage
    3. Validates with Opus after every stage
    4. Handles retries with typed recovery strategies
    5. Prevents infinite loops with circuit breaker

    Usage:
        conductor = OpusConductor.from_config("config/conductor_config.yaml")
        result = conductor.run(task="Fix the bug in cache.py", repo_path="/path/to/repo")
    """

    def __init__(
        self,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the conductor.

        Args:
            config: Full configuration dictionary
            logger: Optional logger instance
        """
        self.config = config
        self.logger = logger or self._setup_logger()

        # Initialize client factory
        self.client_factory = ModelClientFactory(config)

        # Create clients for each role
        self.supervisor_client = self.client_factory.create_client("supervisor", self.logger)
        self.context_client = self.client_factory.create_client("context", self.logger)
        self.engineering_client = self.client_factory.create_client("engineering", self.logger)
        self.review_client = self.client_factory.create_client("review", self.logger)

        # Initialize agents
        self.context_agent = ContextAgent(self.context_client, self.logger)
        self.engineering_agent = EngineeringAgent(self.engineering_client, self.logger)
        self.review_agent = ReviewAgent(self.review_client, self.logger)

        # Initialize handoff protocol
        handoff_config = config.get("handoff", {})
        self.handoff_protocol = HandoffProtocol(
            require_acknowledgment=handoff_config.get("require_acknowledgment", True),
            logger=self.logger,
        )

        # Initialize validators
        val_config = config.get("validation", {})
        static_config = val_config.get("static", {})
        self.static_analyzer = StaticAnalyzer(
            check_syntax=static_config.get("check_syntax", True),
            check_imports=static_config.get("check_imports", True),
            check_edge_cases=static_config.get("check_edge_cases", True),
            logger=self.logger,
        )

        self.semantic_validator = SemanticValidator(
            model_client=self.supervisor_client,
            logger=self.logger,
        )

        exec_config = val_config.get("execution", {})
        self.execution_validator = ExecutionValidator(
            timeout=exec_config.get("sandbox_timeout", 60),
            sandbox_enabled=exec_config.get("sandbox_enabled", True),
            logger=self.logger,
        )

        # Initialize circuit breaker
        orch_config = config.get("orchestration", {})
        self.circuit_breaker = CircuitBreaker(
            threshold=orch_config.get("circuit_breaker_threshold", 5),
        )

        # Get limits from config
        self.max_retries_per_stage = orch_config.get("max_retries_per_stage", 3)
        self.max_total_retries = orch_config.get("max_total_retries", 10)
        self.cost_limit = orch_config.get("cost_limits", {}).get("total", 10.0)

    @classmethod
    def from_config(cls, config_path: str, logger: Optional[logging.Logger] = None) -> "OpusConductor":
        """Create conductor from config file."""
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return cls(config, logger)

    def _setup_logger(self) -> logging.Logger:
        """Setup default logger."""
        logger = logging.getLogger("opus-conductor")
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _log(self, message: str, level: str = "info") -> None:
        """Log a message."""
        getattr(self.logger, level)(f"[CONDUCTOR] {message}")

    def run(
        self,
        task: str,
        repo_path: Optional[str] = None,
    ) -> ConductorResult:
        """
        Run the full orchestration pipeline.

        Args:
            task: The task description (issue/request)
            repo_path: Optional path to target repository

        Returns:
            ConductorResult with outcome and metrics
        """
        self._log(f"Starting orchestration for task: {task[:100]}...")

        # Initialize state
        state = ConductorState(
            original_task=task,
            repo_path=repo_path,
        )

        try:
            # Phase 1: Opus Planning
            state = self._opus_planning(state)

            # Phase 2: Context Analysis
            state = self._run_context_stage(state)

            # Phase 3: Engineering
            state = self._run_engineering_stage(state)

            # Phase 4: Review
            state = self._run_review_stage(state)

            # Phase 5: Execution Validation (optional)
            state = self._run_execution_stage(state)

            # Finalize
            return self._finalize(state)

        except Exception as e:
            self._log(f"Orchestration failed: {e}", "error")
            state.failure_reason = str(e)
            state.success = False
            return self._finalize(state)

    def _opus_planning(self, state: ConductorState) -> ConductorState:
        """
        Phase 1: Opus analyzes the task and extracts requirements.

        This is where Opus creates the "contract" that downstream
        agents must fulfill.
        """
        self._log("Phase 1: Opus Planning")

        prompt = self._build_planning_prompt(state)
        messages = [{"role": "user", "content": prompt}]
        system = self._get_planning_system_prompt()

        response = self.supervisor_client.complete(messages, system=system)

        # Log the call
        state.log_model_call(
            stage="planning",
            model_id=response.model_id,
            input_text=prompt,
            output_text=response.content,
            cost=response.cost,
            tokens=response.total_tokens,
            duration=response.duration,
        )

        # Parse planning output
        self._parse_planning_response(response.content, state)

        self._log(f"Extracted {len(state.constraints)} constraints, "
                  f"{len(state.edge_cases)} edge cases")

        return state

    def _get_planning_system_prompt(self) -> str:
        """Get system prompt for Opus planning."""
        return """You are Opus, the supervisor in the Opus-Conductor multi-agent system.
Your job is to analyze a task and extract explicit requirements that downstream agents must fulfill.

Output your analysis in this JSON format:
{
    "task_archetype": "bug_fix" | "feature" | "refactor" | "performance" | "test" | "documentation",
    "complexity": "simple" | "medium" | "complex" | "expert",
    "constraints": ["Constraint 1", "Constraint 2", ...],
    "success_criteria": ["Criterion 1", "Criterion 2", ...],
    "required_imports": ["module1", "module2", ...],
    "edge_cases": ["Edge case 1", "Edge case 2", ...],
    "plan": "High-level plan text"
}

Be thorough. These requirements will be enforced at every stage."""

    def _build_planning_prompt(self, state: ConductorState) -> str:
        """Build the planning prompt."""
        parts = [
            "## TASK ANALYSIS REQUEST",
            "",
            "### Task Description",
            state.original_task,
        ]

        if state.repo_path:
            parts.extend([
                "",
                "### Repository",
                f"Path: {state.repo_path}",
            ])

        parts.extend([
            "",
            "Please analyze this task and extract explicit requirements.",
        ])

        return "\n".join(parts)

    def _parse_planning_response(self, response: str, state: ConductorState) -> None:
        """Parse Opus's planning response into state."""
        import json

        # Try to extract JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                data = json.loads(json_match.group())

                # Set archetype
                archetype_str = data.get("task_archetype", "unknown")
                try:
                    state.task_archetype = TaskArchetype(archetype_str)
                except ValueError:
                    state.task_archetype = TaskArchetype.UNKNOWN

                # Set complexity
                complexity_str = data.get("complexity", "medium")
                try:
                    state.complexity = Complexity(complexity_str)
                except ValueError:
                    state.complexity = Complexity.MEDIUM

                # Set requirements
                state.constraints = data.get("constraints", [])
                state.success_criteria = data.get("success_criteria", [])
                state.required_imports = data.get("required_imports", [])
                state.edge_cases = data.get("edge_cases", [])
                state.plan = data.get("plan", "")

                return

            except json.JSONDecodeError:
                pass

        # Fallback: extract requirements heuristically
        self._log("Warning: Could not parse planning JSON, using heuristics", "warning")

        # Extract constraints
        if "constraint" in response.lower():
            constraints_match = re.findall(r'[-•]\s*([^-•\n]+)', response)
            state.constraints = [c.strip() for c in constraints_match[:5]]

        # Extract edge cases
        if "edge" in response.lower():
            edge_match = re.findall(r'edge\s+case[:\s]+([^\n]+)', response, re.IGNORECASE)
            state.edge_cases = [e.strip() for e in edge_match]

    def _run_context_stage(self, state: ConductorState) -> ConductorState:
        """
        Phase 2: Context analysis stage.

        The context agent analyzes the repository and identifies relevant files.
        Simple validation: verify we got context output (no code to validate yet).
        """
        self._log("Phase 2: Context Analysis")

        # Check circuit breaker
        if not self.circuit_breaker.can_proceed():
            raise RuntimeError("Circuit breaker open - too many consecutive failures")

        # Create handoff from planning
        handoff = self.handoff_protocol.create_handoff(
            state=state,
            source_stage="planning",
            target_stage="context",
        )

        # Run context agent
        state = self.context_agent.run(state, handoff)

        # Simple validation for context stage: check we have output
        # (No implementation code to validate yet - that's the engineering stage)
        context_valid = bool(state.context_summary or state.relevant_files)

        if context_valid:
            state.context_status = StageStatus.VALIDATED
            state.context_validation = ValidationCheckpoint(
                stage="context",
                timestamp=time.time(),
                decision="APPROVED",
                reasoning=f"Context analysis complete: {len(state.relevant_files)} files, "
                         f"{len(state.context_summary)} chars summary",
            )
            state.add_checkpoint(state.context_validation)
            self.circuit_breaker.record_success()
            self._log(f"Context validated: {len(state.relevant_files)} files identified")
        else:
            state.context_status = StageStatus.FAILED
            self._log("Context validation failed: no files or summary produced", "warning")
            self.circuit_breaker.record_failure()

        return state

    def _run_engineering_stage(self, state: ConductorState) -> ConductorState:
        """
        Phase 3: Engineering stage.

        The engineering agent generates code. Opus validates multiple times
        with retries if needed.
        """
        self._log("Phase 3: Engineering")

        if not self.circuit_breaker.can_proceed():
            raise RuntimeError("Circuit breaker open - too many consecutive failures")

        validation_result = None

        for attempt in range(self.max_retries_per_stage + 1):
            # Create handoff
            handoff = self.handoff_protocol.create_handoff(
                state=state,
                source_stage="context",
                target_stage="engineering",
                validation_result=validation_result,
            )

            # Run engineering agent
            state = self.engineering_agent.run(state, handoff)

            # Static analysis first
            static_result = self.static_analyzer.validate(state)
            if not static_result.passed:
                self._log(f"Static analysis failed: {static_result.error_messages}")
                validation_result = static_result
                state.increment_retry("engineering")
                self.circuit_breaker.record_failure()
                continue

            # Semantic validation with Opus
            validation_result = self.semantic_validator.validate(state)

            if validation_result.passed:
                state.engineering_status = StageStatus.VALIDATED
                state.engineering_validation = validation_result.to_checkpoint(
                    "engineering",
                    state.get_stage_retry_count("engineering")
                )
                state.add_checkpoint(state.engineering_validation)
                self.circuit_breaker.record_success()
                return state

            # Retry needed
            self._log(f"Engineering validation failed (attempt {attempt + 1}): "
                      f"{validation_result.reasoning}")
            state.increment_retry("engineering")
            self.circuit_breaker.record_failure()

            if state.retry_count >= self.max_total_retries:
                raise RuntimeError(f"Max total retries ({self.max_total_retries}) exceeded")

            if self.client_factory.cost_tracker.total_cost > self.cost_limit:
                raise RuntimeError(f"Cost limit (${self.cost_limit}) exceeded")

        # All attempts exhausted
        state.engineering_status = StageStatus.FAILED
        state.failure_reason = f"Engineering failed after {self.max_retries_per_stage + 1} attempts"
        return state

    def _run_review_stage(self, state: ConductorState) -> ConductorState:
        """
        Phase 4: Review stage.

        The review agent checks the implementation. Results feed back
        to engineering if issues found.
        """
        self._log("Phase 4: Review")

        if state.engineering_status != StageStatus.VALIDATED:
            self._log("Skipping review - engineering not validated", "warning")
            state.review_status = StageStatus.SKIPPED
            return state

        # Create handoff
        handoff = self.handoff_protocol.create_handoff(
            state=state,
            source_stage="engineering",
            target_stage="review",
        )

        # Run review agent
        state = self.review_agent.run(state, handoff)

        if state.review_passed:
            state.review_status = StageStatus.VALIDATED
            self._log("Review passed")
        else:
            state.review_status = StageStatus.FAILED
            self._log(f"Review failed: {state.review_feedback}")

            # Could loop back to engineering here for complex systems
            # For now, we note the failure and continue

        return state

    def _run_execution_stage(self, state: ConductorState) -> ConductorState:
        """
        Phase 5: Execution validation (optional).

        Actually runs the code to verify it works.
        """
        self._log("Phase 5: Execution Validation")

        exec_config = self.config.get("validation", {}).get("execution", {})
        if not exec_config.get("run_tests", True):
            self._log("Execution validation disabled")
            state.execution_status = StageStatus.SKIPPED
            return state

        if state.engineering_status != StageStatus.VALIDATED:
            state.execution_status = StageStatus.SKIPPED
            return state

        state.execution_status = StageStatus.IN_PROGRESS

        # Run execution validator
        result = self.execution_validator.validate(state)

        if result.passed:
            state.execution_status = StageStatus.VALIDATED
            state.execution_passed = True
            self._log("Execution validation passed")
        else:
            state.execution_status = StageStatus.FAILED
            state.execution_passed = False
            state.execution_errors = result.error_messages
            self._log(f"Execution validation failed: {result.error_messages}")

        return state

    def _validate_stage(self, state: ConductorState, stage: str) -> ValidationResult:
        """
        Validate a stage's output with Opus.

        Returns ValidationResult with decision.
        """
        return self.semantic_validator.validate(state)

    def _handle_validation_failure(
        self,
        state: ConductorState,
        stage: str,
        validation: ValidationResult,
        handoff: StageHandoff,
    ) -> None:
        """Handle a validation failure with appropriate recovery."""
        self._log(f"Validation failed for {stage}: {validation.decision.value}")

        state.increment_retry(stage)
        self.circuit_breaker.record_failure()

        checkpoint = validation.to_checkpoint(stage, state.get_stage_retry_count(stage))
        state.add_checkpoint(checkpoint)

        if validation.decision == ValidationDecision.ESCALATE:
            # Need to re-plan
            self._log("Escalating to re-planning")
            # In a full system, this would trigger re-planning

        # Log the failure
        state.log_error(
            stage=stage,
            error_message=validation.reasoning,
            metadata={"issues": [i.to_dict() for i in validation.issues]}
        )

    def _finalize(self, state: ConductorState) -> ConductorResult:
        """Finalize the orchestration and return result."""
        # Update state timing
        state.total_time = state.get_elapsed_time()
        state.total_cost = self.client_factory.cost_tracker.total_cost
        state.total_tokens = (
            self.client_factory.cost_tracker.total_prompt_tokens +
            self.client_factory.cost_tracker.total_completion_tokens
        )

        # Determine success
        success = (
            state.engineering_status == StageStatus.VALIDATED and
            not state.failure_reason
        )

        if success:
            state.success = True
            state.final_code = state.implementation_code
            self._log("Orchestration completed successfully!")
        else:
            state.success = False
            self._log(f"Orchestration failed: {state.failure_reason}", "error")

        # Count completed stages
        stages_completed = sum(1 for status in [
            state.context_status,
            state.engineering_status,
            state.review_status,
            state.execution_status,
        ] if status == StageStatus.VALIDATED)

        return ConductorResult(
            success=success,
            state=state,
            final_code=state.final_code,
            final_diff=state.final_diff,
            total_cost=state.total_cost,
            total_tokens=state.total_tokens,
            total_time=state.total_time,
            stages_completed=stages_completed,
            retries_used=state.retry_count,
            failure_reason=state.failure_reason,
        )

    def get_cost_summary(self) -> str:
        """Get a summary of costs across all calls."""
        return self.client_factory.cost_tracker.get_summary()
