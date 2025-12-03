"""
Tests for data_types.py - Dataclasses.
"""

import os
import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_types import (
    Strategy,
    PatchCandidate,
    ExecutionResult,
    VerificationResult,
    EnsembleResult,
)


class TestStrategy:
    """Tests for Strategy enum."""

    def test_all_strategies_exist(self):
        """All 5 strategies are defined."""
        strategies = list(Strategy)
        assert len(strategies) == 5

    def test_strategy_values(self):
        """Strategy values match expected."""
        assert Strategy.MINIMAL.value == "minimal"
        assert Strategy.EXTENDED_THINKING.value == "extended_thinking"
        assert Strategy.TEST_DRIVEN.value == "test_driven"
        assert Strategy.REFACTOR_SAFE.value == "refactor_safe"
        assert Strategy.HIGH_TEMPERATURE.value == "high_temperature"


class TestPatchCandidate:
    """Tests for PatchCandidate dataclass."""

    def test_create_patch_candidate(self):
        """Can create a PatchCandidate."""
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def foo(): pass",
            raw_response="Here's the fix...",
            model_id="test-model",
        )
        assert patch.instance_id == 0
        assert patch.strategy == Strategy.MINIMAL
        assert patch.code == "def foo(): pass"
        assert patch.model_id == "test-model"

    def test_default_values(self):
        """Default values are correct."""
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="",
            raw_response="",
            model_id="test",
        )
        assert patch.input_tokens == 0
        assert patch.output_tokens == 0
        assert patch.cost == 0.0
        assert patch.generation_time_seconds == 0.0

    def test_with_metrics(self):
        """Can set metrics."""
        patch = PatchCandidate(
            instance_id=1,
            strategy=Strategy.EXTENDED_THINKING,
            code="def fix(): return True",
            raw_response="response",
            model_id="opus",
            input_tokens=1000,
            output_tokens=500,
            cost=0.15,
            generation_time_seconds=5.2,
        )
        assert patch.input_tokens == 1000
        assert patch.output_tokens == 500
        assert patch.cost == 0.15
        assert patch.generation_time_seconds == 5.2


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_successful_execution(self):
        """Successful execution has correct values."""
        result = ExecutionResult(
            success=True,
            stdout="test output",
            stderr="",
            return_code=0,
        )
        assert result.success is True
        assert result.stdout == "test output"
        assert result.return_code == 0
        assert result.timed_out is False

    def test_failed_execution(self):
        """Failed execution has correct values."""
        result = ExecutionResult(
            success=False,
            stdout="",
            stderr="Error: something failed",
            return_code=1,
        )
        assert result.success is False
        assert result.stderr == "Error: something failed"
        assert result.return_code == 1

    def test_timeout_execution(self):
        """Timed out execution has correct values."""
        result = ExecutionResult(
            success=False,
            timed_out=True,
            execution_time_seconds=30.0,
        )
        assert result.success is False
        assert result.timed_out is True
        assert result.execution_time_seconds == 30.0


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_default_values(self):
        """Default values are all False."""
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="",
            raw_response="",
            model_id="test",
        )
        result = VerificationResult(patch=patch)
        assert result.syntax_valid is False
        assert result.patch_applies is False
        assert result.reproduction_passes is False
        assert result.regression_passes is False

    def test_passed_all_property_false(self):
        """passed_all is False when any stage fails."""
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def x(): pass",
            raw_response="",
            model_id="test",
        )
        result = VerificationResult(
            patch=patch,
            syntax_valid=True,
            patch_applies=True,
            reproduction_passes=False,  # Fails here
            regression_passes=True,
        )
        assert result.passed_all is False

    def test_passed_all_property_true(self):
        """passed_all is True when all stages pass."""
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def x(): pass",
            raw_response="",
            model_id="test",
        )
        result = VerificationResult(
            patch=patch,
            syntax_valid=True,
            patch_applies=True,
            reproduction_passes=True,
            regression_passes=True,
        )
        assert result.passed_all is True

    def test_pass_rate_zero_when_no_tests(self):
        """pass_rate is 0.0 when no tests run."""
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="",
            raw_response="",
            model_id="test",
        )
        result = VerificationResult(
            patch=patch,
            tests_passed=0,
            tests_total=0,
        )
        assert result.pass_rate == 0.0

    def test_pass_rate_calculation(self):
        """pass_rate is correctly calculated."""
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="",
            raw_response="",
            model_id="test",
        )
        result = VerificationResult(
            patch=patch,
            tests_passed=8,
            tests_total=10,
        )
        assert result.pass_rate == 0.8


class TestEnsembleResult:
    """Tests for EnsembleResult dataclass."""

    def test_successful_result(self):
        """Successful result has all fields."""
        result = EnsembleResult(
            success=True,
            final_patch="--- a/file.py\n+++ b/file.py\n...",
            final_code="def fixed(): pass",
            total_patches_generated=40,
            patches_syntax_valid=38,
            patches_apply_clean=35,
            patches_repro_pass=20,
            patches_regression_pass=15,
            winning_strategy=Strategy.MINIMAL,
            winning_instance_id=7,
            total_cost=1.50,
            total_time_seconds=120.5,
        )
        assert result.success is True
        assert result.final_patch is not None
        assert result.winning_strategy == Strategy.MINIMAL
        assert result.winning_instance_id == 7

    def test_failed_result(self):
        """Failed result has error message."""
        result = EnsembleResult(
            success=False,
            total_patches_generated=40,
            patches_syntax_valid=10,
            patches_apply_clean=5,
            patches_repro_pass=0,
            patches_regression_pass=0,
            error_message="No patches passed reproduction test",
        )
        assert result.success is False
        assert result.final_patch is None
        assert result.error_message is not None

    def test_default_values(self):
        """Default values are correct."""
        result = EnsembleResult(success=False)
        assert result.total_patches_generated == 0
        assert result.total_cost == 0.0
        assert result.correction_iterations == 0
        assert result.all_verifications == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
