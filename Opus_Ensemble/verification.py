"""
Execution-based verification - Phase 4 of the Opus Ensemble.

4-stage pipeline:
1. Syntax check (AST parse)
2. Patch application (simulate)
3. Reproduction test (must pass)
4. Regression tests (must not break existing)
"""

import ast
import logging
import re
import subprocess
import tempfile
import time
from typing import List, Tuple, Optional
from pathlib import Path

try:
    from .data_types import PatchCandidate, VerificationResult, ExecutionResult
except ImportError:
    from data_types import PatchCandidate, VerificationResult, ExecutionResult


class CodeExecutor:
    """Execute Python code safely with timeout."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def execute(self, code: str) -> ExecutionResult:
        """
        Execute Python code and return result.

        Args:
            code: Python code to execute

        Returns:
            ExecutionResult with stdout, stderr, success status
        """
        start = time.time()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            result = subprocess.run(
                ['python', temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            elapsed = time.time() - start

            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                timed_out=False,
                execution_time_seconds=elapsed,
            )

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {self.timeout}s",
                return_code=-1,
                timed_out=True,
                execution_time_seconds=elapsed,
            )

        except Exception as e:
            elapsed = time.time() - start
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                timed_out=False,
                execution_time_seconds=elapsed,
            )

        finally:
            Path(temp_path).unlink(missing_ok=True)


class Verifier:
    """
    Verify patches through the 4-stage pipeline.
    """

    def __init__(self, timeout: int = 30):
        self.executor = CodeExecutor(timeout)

    def verify(
        self,
        patch: PatchCandidate,
        test_code: str = "",
    ) -> VerificationResult:
        """
        Run a patch through all verification stages.

        Args:
            patch: The patch candidate to verify
            test_code: Test code to run against the patch

        Returns:
            VerificationResult with all stage results
        """
        result = VerificationResult(patch=patch)

        # Stage 1: Syntax check
        syntax_valid, syntax_error = self._check_syntax(patch.code)
        result.syntax_valid = syntax_valid
        result.syntax_error = syntax_error

        if not syntax_valid:
            return result

        # Stage 2: Patch applies (for standalone code, always passes)
        result.patch_applies = True

        # Stage 3: Reproduction test
        if test_code:
            full_code = patch.code + "\n\n" + test_code
            exec_result = self.executor.execute(full_code)

            result.reproduction_passes = exec_result.success
            result.reproduction_output = exec_result.stdout + exec_result.stderr
        else:
            # No test code = assume passes
            result.reproduction_passes = True
            result.reproduction_output = "No test code provided"

        if not result.reproduction_passes:
            return result

        # Stage 4: Regression tests (for standalone code tasks, skip)
        result.regression_passes = True
        result.tests_passed = 1 if result.reproduction_passes else 0
        result.tests_total = 1 if test_code else 0

        return result

    def verify_all(
        self,
        patches: List[PatchCandidate],
        test_code: str = "",
    ) -> List[VerificationResult]:
        """
        Verify all patches and return results.

        Args:
            patches: List of patches to verify
            test_code: Test code to run

        Returns:
            List of VerificationResult objects
        """
        results = []
        for patch in patches:
            result = self.verify(patch, test_code)
            results.append(result)
        return results

    def filter_passing(
        self,
        results: List[VerificationResult],
    ) -> Tuple[List[VerificationResult], List[VerificationResult]]:
        """
        Split results into passing and failing.

        Args:
            results: All verification results

        Returns:
            Tuple of (passing, failing) lists
        """
        passing = [r for r in results if r.passed_all]
        failing = [r for r in results if not r.passed_all]
        return passing, failing

    def rank_passing(
        self,
        passing: List[VerificationResult],
    ) -> List[VerificationResult]:
        """
        Rank passing patches by quality.

        Ranking criteria:
        1. Test pass rate (higher = better)
        2. Code size (smaller = better, Occam's razor)

        Args:
            passing: List of passing verification results

        Returns:
            Sorted list (best first)
        """
        def score(r: VerificationResult) -> Tuple[float, int]:
            # Higher pass rate is better
            pass_rate = r.pass_rate
            # Smaller code is better (negative so smaller is "higher")
            code_size = -len(r.patch.code)
            return (pass_rate, code_size)

        return sorted(passing, key=score, reverse=True)

    def _check_syntax(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Check if code has valid Python syntax.

        Args:
            code: Python code to check

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, str(e)


def verify_patches(
    patches: List[PatchCandidate],
    test_code: str = "",
    timeout: int = 30,
) -> Tuple[List[VerificationResult], List[VerificationResult]]:
    """
    Convenience function to verify patches and return (passing, failing).

    Args:
        patches: List of patches to verify
        test_code: Test code to run
        timeout: Execution timeout per patch

    Returns:
        Tuple of (passing, failing) verification results
    """
    verifier = Verifier(timeout)
    results = verifier.verify_all(patches, test_code)
    return verifier.filter_passing(results)


class DockerVerifier:
    """
    Docker-based verification for SWE-bench patches.

    This verifier uses Docker containers to:
    1. Apply git patches
    2. Run the test suite
    3. Check for pass/fail

    This is the correct way to verify patches for SWE-bench.
    """

    def __init__(
        self,
        docker_executor,
        test_cmd: str = "python -m pytest",
        timeout: int = 300,
        logger=None
    ):
        """
        Initialize Docker verifier.

        Args:
            docker_executor: DockerExecutor instance with container running
            test_cmd: Command to run tests
            timeout: Timeout for test execution
            logger: Optional logger
        """
        self.executor = docker_executor
        self.test_cmd = test_cmd
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)

    def verify(self, patch: PatchCandidate) -> VerificationResult:
        """
        Verify a single patch in Docker.

        Args:
            patch: Patch candidate to verify

        Returns:
            VerificationResult with pass/fail status
        """
        result = VerificationResult(patch=patch)

        # Get the patch content - use .code which has the extracted diff
        # (raw_response has full markdown wrapper, code has just the diff)
        patch_content = patch.code
        if not patch_content or not patch_content.strip():
            result.syntax_error = "Empty patch"
            return result

        # Stage 1: Reset repository to clean state
        reset_result = self.executor.reset_repo()
        if not reset_result.success:
            result.syntax_error = f"Failed to reset repo: {reset_result.output}"
            return result

        # Stage 2: Apply patch
        apply_result = self.executor.apply_patch(patch_content)
        if apply_result.success:
            result.syntax_valid = True
            result.patch_applies = True
        else:
            result.syntax_valid = True  # Patch format is valid
            result.patch_applies = False
            # Log first 200 chars of patch for debugging
            patch_preview = patch_content[:200].replace('\n', '\\n')
            result.patch_error = f"Patch failed to apply: {apply_result.output[:500]}\nPatch preview: {patch_preview}"
            self.logger.debug(f"Patch apply failed. Patch content:\n{patch_content[:500]}")
            return result

        # Stage 3: Run tests
        test_result = self.executor.run_tests(self.test_cmd, timeout=self.timeout)

        # Parse test output to determine pass/fail
        output = test_result.output.lower()

        if test_result.timed_out:
            result.reproduction_passes = False
            result.reproduction_output = f"Tests timed out after {self.timeout}s"
        elif test_result.success:
            result.reproduction_passes = True
            result.reproduction_output = test_result.output
            result.regression_passes = True
        else:
            # Check if tests ran but some failed vs complete failure
            if "passed" in output or "failed" in output or "error" in output:
                # Tests ran but some failed
                result.reproduction_passes = False
                result.reproduction_output = test_result.output
            else:
                # Complete failure (import error, syntax error, etc.)
                result.reproduction_passes = False
                result.reproduction_output = f"Tests failed to run: {test_result.output}"

        # Extract test counts if available
        import re
        passed_match = re.search(r'(\d+) passed', test_result.output)
        failed_match = re.search(r'(\d+) failed', test_result.output)

        if passed_match:
            result.tests_passed = int(passed_match.group(1))
        if failed_match or passed_match:
            total = result.tests_passed
            if failed_match:
                total += int(failed_match.group(1))
            result.tests_total = total

        return result

    def verify_all(
        self,
        patches: List[PatchCandidate],
    ) -> List[VerificationResult]:
        """
        Verify all patches sequentially in Docker.

        Args:
            patches: List of patches to verify

        Returns:
            List of VerificationResult objects
        """
        results = []
        for i, patch in enumerate(patches):
            self.logger.debug(f"Verifying patch {i+1}/{len(patches)}")
            result = self.verify(patch)
            results.append(result)
        return results

    def filter_passing(
        self,
        results: List[VerificationResult],
    ) -> Tuple[List[VerificationResult], List[VerificationResult]]:
        """
        Split results into passing and failing.

        Args:
            results: All verification results

        Returns:
            Tuple of (passing, failing) lists
        """
        passing = [r for r in results if r.passed_all]
        failing = [r for r in results if not r.passed_all]
        return passing, failing

    def rank_passing(
        self,
        passing: List[VerificationResult],
    ) -> List[VerificationResult]:
        """
        Rank passing patches by quality.

        Args:
            passing: List of passing verification results

        Returns:
            Sorted list (best first)
        """
        def score(r: VerificationResult) -> Tuple[float, int]:
            pass_rate = r.pass_rate
            code_size = -len(r.patch.code)
            return (pass_rate, code_size)

        return sorted(passing, key=score, reverse=True)
