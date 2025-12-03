"""
Tests for verification.py - Execution-based verification.
"""

import os
import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_types import Strategy, PatchCandidate, VerificationResult
from verification import CodeExecutor, Verifier, verify_patches


class TestCodeExecutor:
    """Tests for CodeExecutor class."""

    def test_execute_valid_python(self):
        """Execute valid Python code."""
        executor = CodeExecutor(timeout=10)
        result = executor.execute("print('hello')")
        assert result.success is True
        assert "hello" in result.stdout
        assert result.return_code == 0

    def test_execute_syntax_error(self):
        """Execute code with syntax error fails."""
        executor = CodeExecutor(timeout=10)
        result = executor.execute("def broken(")
        assert result.success is False
        assert result.return_code != 0

    def test_execute_runtime_error(self):
        """Execute code with runtime error fails."""
        executor = CodeExecutor(timeout=10)
        result = executor.execute("raise ValueError('test error')")
        assert result.success is False
        assert "ValueError" in result.stderr

    def test_execute_timeout(self):
        """Execute code that times out."""
        executor = CodeExecutor(timeout=1)
        result = executor.execute("import time; time.sleep(10)")
        assert result.success is False
        assert result.timed_out is True

    def test_execution_time_tracked(self):
        """Execution time is tracked."""
        executor = CodeExecutor(timeout=10)
        result = executor.execute("x = 1 + 1")
        assert result.execution_time_seconds >= 0


class TestVerifier:
    """Tests for Verifier class."""

    def test_syntax_check_valid(self):
        """Valid syntax passes check."""
        verifier = Verifier(timeout=10)
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def foo():\n    return 42",
            raw_response="",
            model_id="test",
        )
        result = verifier.verify(patch)
        assert result.syntax_valid is True
        assert result.syntax_error is None

    def test_syntax_check_invalid(self):
        """Invalid syntax fails check."""
        verifier = Verifier(timeout=10)
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def foo(\n    return 42",  # Missing closing paren
            raw_response="",
            model_id="test",
        )
        result = verifier.verify(patch)
        assert result.syntax_valid is False
        assert result.syntax_error is not None
        assert "SyntaxError" in result.syntax_error

    def test_verify_with_passing_test(self):
        """Verification with passing test succeeds."""
        verifier = Verifier(timeout=10)
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def add(a, b):\n    return a + b",
            raw_response="",
            model_id="test",
        )
        test_code = "assert add(1, 2) == 3"
        result = verifier.verify(patch, test_code)
        assert result.syntax_valid is True
        assert result.patch_applies is True
        assert result.reproduction_passes is True
        assert result.passed_all is True

    def test_verify_with_failing_test(self):
        """Verification with failing test fails."""
        verifier = Verifier(timeout=10)
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def add(a, b):\n    return a - b",  # Wrong implementation
            raw_response="",
            model_id="test",
        )
        test_code = "assert add(1, 2) == 3"
        result = verifier.verify(patch, test_code)
        assert result.syntax_valid is True
        assert result.reproduction_passes is False
        assert result.passed_all is False

    def test_verify_no_test_code(self):
        """Verification without test code assumes pass."""
        verifier = Verifier(timeout=10)
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def foo(): pass",
            raw_response="",
            model_id="test",
        )
        result = verifier.verify(patch)
        assert result.reproduction_passes is True
        assert "No test code" in result.reproduction_output


class TestVerifyAll:
    """Tests for verify_all method."""

    def test_verify_multiple_patches(self):
        """Verify multiple patches at once."""
        verifier = Verifier(timeout=10)
        patches = [
            PatchCandidate(
                instance_id=0,
                strategy=Strategy.MINIMAL,
                code="def add(a, b): return a + b",
                raw_response="",
                model_id="test",
            ),
            PatchCandidate(
                instance_id=1,
                strategy=Strategy.EXTENDED_THINKING,
                code="def add(a, b): return a - b",  # Wrong
                raw_response="",
                model_id="test",
            ),
            PatchCandidate(
                instance_id=2,
                strategy=Strategy.TEST_DRIVEN,
                code="def broken(",  # Syntax error
                raw_response="",
                model_id="test",
            ),
        ]
        test_code = "assert add(2, 3) == 5"
        results = verifier.verify_all(patches, test_code)

        assert len(results) == 3
        assert results[0].passed_all is True  # Correct
        assert results[1].passed_all is False  # Wrong logic
        assert results[2].passed_all is False  # Syntax error


class TestFilterPassing:
    """Tests for filter_passing method."""

    def test_filter_passing_and_failing(self):
        """Filter separates passing from failing."""
        verifier = Verifier(timeout=10)

        patches = [
            PatchCandidate(
                instance_id=i,
                strategy=Strategy.MINIMAL,
                code=f"def add(a, b): return a + b" if i % 2 == 0 else "def broken(",
                raw_response="",
                model_id="test",
            )
            for i in range(4)
        ]

        results = verifier.verify_all(patches)
        passing, failing = verifier.filter_passing(results)

        assert len(passing) == 2  # instances 0, 2
        assert len(failing) == 2  # instances 1, 3


class TestRankPassing:
    """Tests for rank_passing method."""

    def test_rank_by_code_size(self):
        """Smaller code ranks higher."""
        verifier = Verifier(timeout=10)

        # Create patches of different sizes
        small_patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def f(): return 1",
            raw_response="",
            model_id="test",
        )
        large_patch = PatchCandidate(
            instance_id=1,
            strategy=Strategy.REFACTOR_SAFE,
            code="def f():\n    # A very long comment\n    x = 1\n    return x",
            raw_response="",
            model_id="test",
        )

        results = [
            VerificationResult(
                patch=large_patch,
                syntax_valid=True,
                patch_applies=True,
                reproduction_passes=True,
                regression_passes=True,
                tests_passed=1,
                tests_total=1,
            ),
            VerificationResult(
                patch=small_patch,
                syntax_valid=True,
                patch_applies=True,
                reproduction_passes=True,
                regression_passes=True,
                tests_passed=1,
                tests_total=1,
            ),
        ]

        ranked = verifier.rank_passing(results)
        # Smaller code should rank first (when pass rate is equal)
        assert ranked[0].patch.instance_id == 0  # small_patch


class TestVerifyPatchesConvenience:
    """Tests for verify_patches convenience function."""

    def test_returns_passing_and_failing(self):
        """Convenience function returns tuple of passing and failing."""
        patches = [
            PatchCandidate(
                instance_id=0,
                strategy=Strategy.MINIMAL,
                code="x = 1",
                raw_response="",
                model_id="test",
            ),
            PatchCandidate(
                instance_id=1,
                strategy=Strategy.MINIMAL,
                code="def broken(",
                raw_response="",
                model_id="test",
            ),
        ]

        passing, failing = verify_patches(patches)
        assert len(passing) == 1
        assert len(failing) == 1
        assert passing[0].patch.instance_id == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
