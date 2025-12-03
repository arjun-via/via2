"""
=============================================================================
SCRIPT NAME: test_state.py
=============================================================================

Unit tests for Opus-Conductor state management.

Tests cover:
- State initialization and defaults
- Stage status transitions
- Validation checkpoint creation
- Audit event logging
- Import verification
- Edge case tracking
- Serialization (to_dict, save, load)
- State helper methods

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import pytest
import json
import tempfile
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from conductor.state import (
    StageStatus,
    TaskArchetype,
    Complexity,
    ValidationCheckpoint,
    AuditEvent,
    ConductorState,
)


class TestStageStatus:
    """Test StageStatus enum."""

    def test_all_statuses_exist(self):
        """All expected statuses should be defined."""
        assert StageStatus.PENDING.value == "pending"
        assert StageStatus.IN_PROGRESS.value == "in_progress"
        assert StageStatus.VALIDATED.value == "validated"
        assert StageStatus.FAILED.value == "failed"
        assert StageStatus.SKIPPED.value == "skipped"

    def test_status_from_string(self):
        """Should create status from string value."""
        assert StageStatus("pending") == StageStatus.PENDING
        assert StageStatus("validated") == StageStatus.VALIDATED


class TestTaskArchetype:
    """Test TaskArchetype enum."""

    def test_all_archetypes_exist(self):
        """All expected archetypes should be defined."""
        archetypes = [a.value for a in TaskArchetype]
        assert "bug_fix" in archetypes
        assert "feature" in archetypes
        assert "refactor" in archetypes
        assert "unknown" in archetypes


class TestComplexity:
    """Test Complexity enum."""

    def test_all_complexities_exist(self):
        """All expected complexities should be defined."""
        assert Complexity.SIMPLE.value == "simple"
        assert Complexity.MEDIUM.value == "medium"
        assert Complexity.COMPLEX.value == "complex"
        assert Complexity.EXPERT.value == "expert"


class TestValidationCheckpoint:
    """Test ValidationCheckpoint dataclass."""

    def test_create_checkpoint(self):
        """Should create checkpoint with all fields."""
        cp = ValidationCheckpoint(
            stage="context",
            timestamp=time.time(),
            decision="APPROVED",
            reasoning="All requirements met",
            issues=[],
            guidance=None,
            retry_count=0
        )
        assert cp.stage == "context"
        assert cp.decision == "APPROVED"
        assert cp.issues == []

    def test_checkpoint_with_issues(self):
        """Should create checkpoint with issues."""
        cp = ValidationCheckpoint(
            stage="engineering",
            timestamp=time.time(),
            decision="RETRY",
            reasoning="Missing imports",
            issues=["Missing numpy import", "Missing pandas import"],
            guidance="Add the missing imports at the top",
            retry_count=1
        )
        assert len(cp.issues) == 2
        assert cp.guidance is not None
        assert cp.retry_count == 1

    def test_checkpoint_to_dict(self):
        """Should serialize to dictionary."""
        cp = ValidationCheckpoint(
            stage="review",
            timestamp=1234567890.0,
            decision="ESCALATE",
            reasoning="Cannot be fixed without architecture change",
            issues=["Fundamental design flaw"],
            guidance=None,
            retry_count=3
        )
        d = cp.to_dict()
        assert d["stage"] == "review"
        assert d["timestamp"] == 1234567890.0
        assert d["decision"] == "ESCALATE"
        assert len(d["issues"]) == 1

    def test_checkpoint_from_dict(self):
        """Should deserialize from dictionary."""
        data = {
            "stage": "context",
            "timestamp": 1234567890.0,
            "decision": "APPROVED",
            "reasoning": "Looks good",
            "issues": [],
            "guidance": None,
            "retry_count": 0
        }
        cp = ValidationCheckpoint.from_dict(data)
        assert cp.stage == "context"
        assert cp.decision == "APPROVED"


class TestAuditEvent:
    """Test AuditEvent dataclass."""

    def test_create_event(self):
        """Should create audit event."""
        event = AuditEvent(
            timestamp=time.time(),
            event_type="model_call",
            stage="engineering",
            model_id="claude-opus-4-5",
            input_preview="Write code to...",
            output_preview="def solution()...",
            cost=0.05,
            tokens=1000,
            duration=5.5,
        )
        assert event.event_type == "model_call"
        assert event.cost == 0.05
        assert event.tokens == 1000

    def test_event_to_dict_truncates_preview(self):
        """Should truncate long previews in to_dict."""
        long_text = "x" * 1000
        event = AuditEvent(
            timestamp=time.time(),
            event_type="model_call",
            stage="context",
            input_preview=long_text,
            output_preview=long_text,
        )
        d = event.to_dict()
        assert len(d["input_preview"]) == 500
        assert len(d["output_preview"]) == 500


class TestConductorState:
    """Test ConductorState dataclass."""

    def test_default_initialization(self):
        """Should initialize with sensible defaults."""
        state = ConductorState()
        assert state.task_id is not None
        assert len(state.task_id) == 8
        assert state.original_task == ""
        assert state.task_archetype == TaskArchetype.UNKNOWN
        assert state.complexity == Complexity.MEDIUM
        assert state.context_status == StageStatus.PENDING
        assert state.engineering_status == StageStatus.PENDING
        assert state.review_status == StageStatus.PENDING
        assert state.execution_status == StageStatus.PENDING

    def test_initialization_with_values(self):
        """Should initialize with provided values."""
        state = ConductorState(
            original_task="Fix the bug in cache.py",
            task_archetype=TaskArchetype.BUG_FIX,
            complexity=Complexity.COMPLEX,
            constraints=["Must not break API"],
            success_criteria=["All tests pass"],
        )
        assert state.original_task == "Fix the bug in cache.py"
        assert state.task_archetype == TaskArchetype.BUG_FIX
        assert state.complexity == Complexity.COMPLEX
        assert len(state.constraints) == 1
        assert len(state.success_criteria) == 1

    def test_verify_imports_complete_no_requirements(self):
        """Should return True when no imports required."""
        state = ConductorState()
        assert state.verify_imports_complete() is True

    def test_verify_imports_complete_all_present(self):
        """Should return True when all imports present."""
        state = ConductorState(
            required_imports=["numpy", "pandas"],
            imports_included=["import numpy as np", "import pandas as pd"]
        )
        assert state.verify_imports_complete() is True

    def test_verify_imports_complete_missing(self):
        """Should return False when imports missing."""
        state = ConductorState(
            required_imports=["numpy", "pandas", "scipy"],
            imports_included=["import numpy as np"]
        )
        assert state.verify_imports_complete() is False

    def test_get_missing_imports(self):
        """Should return list of missing imports."""
        state = ConductorState(
            required_imports=["numpy", "pandas", "scipy"],
            imports_included=["import numpy as np", "from scipy import stats"]
        )
        missing = state.get_missing_imports()
        assert "pandas" in missing
        assert "numpy" not in missing
        assert "scipy" not in missing

    def test_verify_edge_cases_handled_no_cases(self):
        """Should return True when no edge cases."""
        state = ConductorState()
        assert state.verify_edge_cases_handled() is True

    def test_verify_edge_cases_handled_all_handled(self):
        """Should return True when all handled."""
        state = ConductorState(
            edge_cases=["empty input", "null values"],
            edge_cases_handled={"empty input": True, "null values": True}
        )
        assert state.verify_edge_cases_handled() is True

    def test_verify_edge_cases_handled_some_missing(self):
        """Should return False when some not handled."""
        state = ConductorState(
            edge_cases=["empty input", "null values", "negative numbers"],
            edge_cases_handled={"empty input": True, "null values": False}
        )
        assert state.verify_edge_cases_handled() is False

    def test_get_unhandled_edge_cases(self):
        """Should return list of unhandled cases."""
        state = ConductorState(
            edge_cases=["empty input", "null values", "negative numbers"],
            edge_cases_handled={"empty input": True}
        )
        unhandled = state.get_unhandled_edge_cases()
        assert "null values" in unhandled
        assert "negative numbers" in unhandled
        assert "empty input" not in unhandled

    def test_add_checkpoint(self):
        """Should add checkpoint to history."""
        state = ConductorState()
        cp = ValidationCheckpoint(
            stage="context",
            timestamp=time.time(),
            decision="APPROVED",
            reasoning="OK"
        )
        state.add_checkpoint(cp)
        assert len(state.checkpoints) == 1
        assert state.checkpoints[0].stage == "context"

    def test_add_audit_event(self):
        """Should add event to history."""
        state = ConductorState()
        event = AuditEvent(
            timestamp=time.time(),
            event_type="stage_start",
            stage="context"
        )
        state.add_audit_event(event)
        assert len(state.audit_events) == 1

    def test_log_model_call(self):
        """Should log model call and update totals."""
        state = ConductorState()
        state.log_model_call(
            stage="engineering",
            model_id="claude-opus",
            input_text="prompt",
            output_text="response",
            cost=0.05,
            tokens=1000,
            duration=2.5
        )
        assert len(state.audit_events) == 1
        assert state.total_cost == 0.05
        assert state.total_tokens == 1000

    def test_log_multiple_model_calls(self):
        """Should accumulate costs across calls."""
        state = ConductorState()
        state.log_model_call("s1", "m1", "in", "out", cost=0.05, tokens=100)
        state.log_model_call("s2", "m2", "in", "out", cost=0.10, tokens=200)
        state.log_model_call("s3", "m3", "in", "out", cost=0.15, tokens=300)
        assert state.total_cost == pytest.approx(0.30, rel=1e-2)
        assert state.total_tokens == 600
        assert len(state.audit_events) == 3

    def test_log_error(self):
        """Should log error event."""
        state = ConductorState()
        state.log_error("engineering", "Syntax error on line 42", {"line": 42})
        assert len(state.audit_events) == 1
        assert state.audit_events[0].event_type == "error"
        assert "Syntax error" in state.audit_events[0].error_message

    def test_increment_retry(self):
        """Should increment retry counts."""
        state = ConductorState()
        count1 = state.increment_retry("engineering")
        count2 = state.increment_retry("engineering")
        count3 = state.increment_retry("review")
        assert count1 == 1
        assert count2 == 2
        assert count3 == 1
        assert state.retry_count == 3
        assert state.get_stage_retry_count("engineering") == 2
        assert state.get_stage_retry_count("review") == 1
        assert state.get_stage_retry_count("context") == 0

    def test_get_elapsed_time(self):
        """Should return elapsed time since start."""
        state = ConductorState()
        time.sleep(0.1)
        elapsed = state.get_elapsed_time()
        assert elapsed >= 0.1

    def test_to_dict(self):
        """Should serialize state to dictionary."""
        state = ConductorState(
            original_task="Test task",
            task_archetype=TaskArchetype.BUG_FIX,
            constraints=["constraint1"],
            success_criteria=["criterion1"],
        )
        d = state.to_dict()
        assert d["original_task"] == "Test task"
        assert d["task_archetype"] == "bug_fix"
        assert "constraint1" in d["constraints"]
        assert "criterion1" in d["success_criteria"]

    def test_save_and_load(self):
        """Should save to file and load back."""
        state = ConductorState(
            original_task="Save/load test",
            task_archetype=TaskArchetype.FEATURE,
            complexity=Complexity.COMPLEX,
            constraints=["must be fast"],
            edge_cases=["empty input"],
            edge_cases_handled={"empty input": True},
        )
        state.log_model_call("context", "gemini", "in", "out", 0.01, 500)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            state.save(filepath)
            loaded = ConductorState.load(filepath)

            assert loaded.original_task == "Save/load test"
            assert loaded.task_archetype == TaskArchetype.FEATURE
            assert loaded.complexity == Complexity.COMPLEX
            assert "must be fast" in loaded.constraints
            assert loaded.edge_cases_handled["empty input"] is True
            assert loaded.total_cost == 0.01
        finally:
            Path(filepath).unlink(missing_ok=True)

    def test_get_summary(self):
        """Should return human-readable summary."""
        state = ConductorState(
            original_task="Summary test",
            task_archetype=TaskArchetype.BUG_FIX,
            required_imports=["numpy"],
            imports_included=["import numpy"],
            edge_cases=["null input", "empty list"],
            edge_cases_handled={"null input": True},
        )
        state.context_status = StageStatus.VALIDATED
        summary = state.get_summary()

        assert "BUG_FIX" in summary or "bug_fix" in summary
        assert "context" in summary.lower()
        assert "Imports: 1 required" in summary


class TestStateIntegration:
    """Integration tests for state workflow."""

    def test_full_workflow_simulation(self):
        """Simulate a complete orchestration workflow."""
        # Initialize state
        state = ConductorState(
            original_task="Fix cache invalidation bug",
            task_archetype=TaskArchetype.BUG_FIX,
            complexity=Complexity.MEDIUM,
            repo_path="/path/to/repo",
        )

        # Opus planning phase - set requirements
        state.constraints = [
            "Must not change public API",
            "Must maintain backward compatibility",
        ]
        state.success_criteria = [
            "Cache properly invalidates on update",
            "All existing tests pass",
        ]
        state.required_imports = ["functools", "time"]
        state.edge_cases = [
            "Empty cache",
            "Concurrent access",
            "Cache entry expiration",
        ]
        state.plan = "1. Identify cache class\n2. Fix invalidation logic\n3. Add tests"

        # Context stage
        state.context_status = StageStatus.IN_PROGRESS
        state.log_model_call("context", "gemini-2.5-pro", "analyze repo", "found files", 0.02, 5000)
        state.relevant_files = ["src/cache.py", "tests/test_cache.py"]
        state.context_summary = "Cache class in src/cache.py has invalidation bug"
        state.context_status = StageStatus.VALIDATED
        state.add_checkpoint(ValidationCheckpoint(
            stage="context",
            timestamp=time.time(),
            decision="APPROVED",
            reasoning="Relevant files identified correctly"
        ))

        # Engineering stage
        state.engineering_status = StageStatus.IN_PROGRESS
        state.log_model_call("engineering", "claude-sonnet", "write fix", "def fix()...", 0.05, 2000)
        state.implementation_code = "def invalidate_cache():\n    pass"
        state.imports_included = ["import functools", "import time"]
        state.edge_cases_handled = {
            "Empty cache": True,
            "Concurrent access": True,
            "Cache entry expiration": False,  # Forgot one!
        }

        # First validation - fails due to missing edge case
        state.add_checkpoint(ValidationCheckpoint(
            stage="engineering",
            timestamp=time.time(),
            decision="RETRY",
            reasoning="Missing edge case handling",
            issues=["Cache entry expiration not handled"],
            guidance="Add expiration check before cache access",
            retry_count=1
        ))
        state.increment_retry("engineering")

        # Retry engineering
        state.log_model_call("engineering", "claude-sonnet", "fix edge case", "updated code", 0.03, 1500)
        state.edge_cases_handled["Cache entry expiration"] = True

        # Now passes
        state.add_checkpoint(ValidationCheckpoint(
            stage="engineering",
            timestamp=time.time(),
            decision="APPROVED",
            reasoning="All requirements met"
        ))
        state.engineering_status = StageStatus.VALIDATED

        # Verify final state
        assert state.verify_imports_complete()
        assert state.verify_edge_cases_handled()
        assert len(state.checkpoints) == 3
        assert state.retry_count == 1
        assert state.total_cost == pytest.approx(0.10, rel=1e-2)
        assert state.context_status == StageStatus.VALIDATED
        assert state.engineering_status == StageStatus.VALIDATED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
