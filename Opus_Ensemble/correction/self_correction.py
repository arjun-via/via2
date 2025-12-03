"""
Self-correction loop for Opus Ensemble.

Iteratively refines patches based on test failures:
1. Take a failing patch + error info
2. Ask LLM to fix based on error
3. Re-verify in Docker
4. Repeat until pass or max iterations

Key insight: execution feedback is gold - use it to guide fixes.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from ..api_client import EnsembleAPIClient as APIClient
    from ..docker_executor import DockerExecutor, ExecutionResult
    from ..data_types import PatchCandidate, VerificationResult
except ImportError:
    from api_client import EnsembleAPIClient as APIClient
    from docker_executor import DockerExecutor, ExecutionResult
    from data_types import PatchCandidate, VerificationResult


# Prompt for analyzing test failures
ERROR_ANALYSIS_PROMPT = """Analyze this test failure and identify the root cause.

## Original Issue
{issue_description}

## Applied Patch
```diff
{patch}
```

## Test Command
{test_cmd}

## Test Output (FAILED)
```
{test_output}
```

## Questions to Answer
1. What specific test(s) failed?
2. What is the expected vs actual behavior?
3. What part of the patch caused this failure?
4. What needs to be fixed?

Provide a brief analysis.
"""

# Prompt for generating fix
FIX_PROMPT = """Fix the failing patch based on the test error.

## Original Issue
{issue_description}

## Current Patch (that failed)
```diff
{patch}
```

## Error Analysis
{error_analysis}

## Test Output
```
{test_output}
```

## Instructions
1. Analyze the test failure carefully
2. Identify what needs to change in the patch
3. Generate a corrected patch that will pass the tests

Output ONLY the corrected unified diff patch, nothing else.

```diff
{patch_hint}
```
"""


@dataclass
class CorrectionConfig:
    """Configuration for self-correction loop."""
    max_iterations: int = 3
    test_timeout: int = 300
    temperature: float = 0.3  # Lower for focused fixes
    max_tokens: int = 4000
    analyze_before_fix: bool = True  # Do error analysis first


@dataclass
class CorrectionResult:
    """Result from self-correction loop."""
    success: bool
    final_patch: Optional[str] = None
    iterations: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


class SelfCorrectionLoop:
    """
    Self-correction loop that iteratively fixes patches.

    The key insight: when a patch fails tests, we have valuable
    information in the error output. Use it to guide the fix.

    Usage:
        loop = SelfCorrectionLoop(
            api_client=client,
            docker_executor=executor
        )

        result = loop.correct(
            patch_candidate=failing_patch,
            issue_description="Fix race condition",
            test_cmd="pytest tests/ -v"
        )

        if result.success:
            print(f"Fixed after {result.iterations} iterations")
            print(result.final_patch)
    """

    def __init__(
        self,
        api_client: APIClient,
        docker_executor: DockerExecutor,
        config: Optional[CorrectionConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize self-correction loop.

        Args:
            api_client: Client for LLM API calls
            docker_executor: Docker executor for running tests
            config: Configuration options
            logger: Logger instance
        """
        self.api_client = api_client
        self.docker_executor = docker_executor
        self.config = config or CorrectionConfig()
        self.logger = logger or logging.getLogger(__name__)

    def _extract_patch(self, response: str) -> Optional[str]:
        """Extract unified diff patch from LLM response."""
        # Try to find diff block
        diff_match = re.search(r'```diff\s*(.*?)```', response, re.DOTALL)
        if diff_match:
            return diff_match.group(1).strip()

        # Try plain code block with diff content
        code_match = re.search(r'```\s*(---.*?)```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Look for diff markers directly
        if '---' in response and '+++' in response:
            # Find from first --- to end
            lines = response.split('\n')
            in_diff = False
            diff_lines = []
            for line in lines:
                if line.startswith('---'):
                    in_diff = True
                if in_diff:
                    diff_lines.append(line)
            if diff_lines:
                return '\n'.join(diff_lines)

        return None

    def _analyze_error(
        self,
        issue_description: str,
        patch: str,
        test_cmd: str,
        test_output: str
    ) -> str:
        """
        Analyze test failure to understand root cause.

        Args:
            issue_description: Original issue
            patch: The failing patch
            test_cmd: Command used to run tests
            test_output: Output from failed tests

        Returns:
            Analysis of what went wrong
        """
        prompt = ERROR_ANALYSIS_PROMPT.format(
            issue_description=issue_description,
            patch=patch,
            test_cmd=test_cmd,
            test_output=test_output[-4000:]  # Limit output size
        )

        try:
            analysis = self.api_client.generate(
                prompt=prompt,
                temperature=0.2,  # Low temp for analysis
                max_tokens=1000
            )
            return analysis
        except Exception as e:
            self.logger.error(f"Error analysis failed: {e}")
            return f"Test failed with output:\n{test_output[-1000:]}"

    def _generate_fix(
        self,
        issue_description: str,
        patch: str,
        error_analysis: str,
        test_output: str
    ) -> Optional[str]:
        """
        Generate a fixed patch based on error analysis.

        Args:
            issue_description: Original issue
            patch: The failing patch
            error_analysis: Analysis of what went wrong
            test_output: Test failure output

        Returns:
            Fixed patch or None
        """
        # Extract file path from patch for hint
        patch_hint = ""
        for line in patch.split('\n'):
            if line.startswith('---'):
                patch_hint = line + "\n"
            elif line.startswith('+++'):
                patch_hint += line
                break

        prompt = FIX_PROMPT.format(
            issue_description=issue_description,
            patch=patch,
            error_analysis=error_analysis,
            test_output=test_output[-3000:],
            patch_hint=patch_hint
        )

        try:
            response = self.api_client.generate(
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            return self._extract_patch(response)
        except Exception as e:
            self.logger.error(f"Fix generation failed: {e}")
            return None

    def _run_tests(
        self,
        patch: str,
        test_cmd: str
    ) -> Tuple[bool, str]:
        """
        Apply patch and run tests.

        Args:
            patch: Unified diff patch
            test_cmd: Command to run tests

        Returns:
            Tuple of (tests_passed, output)
        """
        # Reset repo first
        reset_result = self.docker_executor.reset_repo()
        if not reset_result.success:
            return False, f"Failed to reset repo: {reset_result.stderr}"

        # Apply patch
        apply_result = self.docker_executor.apply_patch(patch)
        if not apply_result.success:
            return False, f"Failed to apply patch: {apply_result.stderr}"

        # Run tests
        test_result = self.docker_executor.run_tests(
            test_cmd,
            timeout=self.config.test_timeout
        )

        tests_passed = test_result.return_code == 0
        output = test_result.stdout + "\n" + test_result.stderr

        return tests_passed, output

    def correct(
        self,
        patch_candidate: PatchCandidate,
        issue_description: str,
        test_cmd: str
    ) -> CorrectionResult:
        """
        Attempt to correct a failing patch.

        Args:
            patch_candidate: The patch that failed verification
            issue_description: Original issue description
            test_cmd: Command to run tests

        Returns:
            CorrectionResult with final patch if successful
        """
        history = []
        current_patch = patch_candidate.patch

        for iteration in range(self.config.max_iterations):
            self.logger.info(f"Correction iteration {iteration + 1}/{self.config.max_iterations}")

            # Run tests with current patch
            tests_passed, test_output = self._run_tests(current_patch, test_cmd)

            iteration_record = {
                "iteration": iteration + 1,
                "patch": current_patch,
                "tests_passed": tests_passed,
                "test_output": test_output[:2000]
            }

            if tests_passed:
                # Success!
                self.logger.info(f"Patch fixed on iteration {iteration + 1}")
                history.append(iteration_record)
                return CorrectionResult(
                    success=True,
                    final_patch=current_patch,
                    iterations=iteration + 1,
                    history=history
                )

            # Analyze error if enabled
            if self.config.analyze_before_fix:
                error_analysis = self._analyze_error(
                    issue_description,
                    current_patch,
                    test_cmd,
                    test_output
                )
                iteration_record["error_analysis"] = error_analysis
            else:
                error_analysis = test_output[-1000:]

            # Generate fix
            fixed_patch = self._generate_fix(
                issue_description,
                current_patch,
                error_analysis,
                test_output
            )

            if not fixed_patch:
                self.logger.warning(f"Iteration {iteration + 1}: No fix generated")
                history.append(iteration_record)
                continue

            # Update for next iteration
            iteration_record["generated_fix"] = fixed_patch
            history.append(iteration_record)
            current_patch = fixed_patch

        # All iterations failed
        return CorrectionResult(
            success=False,
            final_patch=current_patch,
            iterations=self.config.max_iterations,
            history=history,
            error=f"Failed to fix after {self.config.max_iterations} iterations"
        )

    def correct_batch(
        self,
        patches: List[PatchCandidate],
        issue_description: str,
        test_cmd: str
    ) -> List[CorrectionResult]:
        """
        Attempt to correct multiple failing patches.

        Tries each patch independently.

        Args:
            patches: List of failing patches
            issue_description: Original issue
            test_cmd: Test command

        Returns:
            List of CorrectionResult
        """
        results = []
        for i, patch in enumerate(patches):
            self.logger.info(f"Correcting patch {i + 1}/{len(patches)}")
            result = self.correct(patch, issue_description, test_cmd)
            results.append(result)

            # Early exit if we find a working fix
            if result.success:
                self.logger.info(f"Found working fix for patch {i + 1}")
                break

        return results


class ErrorParser:
    """
    Utility class to parse common test error formats.

    Extracts structured information from pytest, unittest output.
    """

    @staticmethod
    def parse_pytest_output(output: str) -> Dict[str, Any]:
        """Parse pytest output for test results."""
        result = {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "failed_tests": [],
            "error_messages": []
        }

        # Parse summary line: "1 failed, 2 passed in 0.5s"
        summary_match = re.search(
            r'(\d+) passed.*?(\d+) failed|(\d+) failed.*?(\d+) passed',
            output
        )
        if summary_match:
            groups = summary_match.groups()
            if groups[0]:
                result["passed"] = int(groups[0])
                result["failed"] = int(groups[1])
            elif groups[2]:
                result["failed"] = int(groups[2])
                result["passed"] = int(groups[3])

        # Extract failed test names
        failed_pattern = r'FAILED\s+(\S+)'
        failed_tests = re.findall(failed_pattern, output)
        result["failed_tests"] = failed_tests

        # Extract assertion errors
        assertion_pattern = r'AssertionError:\s*(.+?)(?:\n|$)'
        assertions = re.findall(assertion_pattern, output)
        result["error_messages"].extend(assertions)

        # Extract exception messages
        exception_pattern = r'(?:Error|Exception):\s*(.+?)(?:\n|$)'
        exceptions = re.findall(exception_pattern, output)
        result["error_messages"].extend(exceptions)

        return result

    @staticmethod
    def extract_traceback(output: str) -> List[str]:
        """Extract Python tracebacks from output."""
        tracebacks = []
        current_tb = []
        in_traceback = False

        for line in output.split('\n'):
            if 'Traceback (most recent call last)' in line:
                if current_tb:
                    tracebacks.append('\n'.join(current_tb))
                current_tb = [line]
                in_traceback = True
            elif in_traceback:
                current_tb.append(line)
                # End of traceback at error line
                if line.strip() and not line.startswith(' ') and ':' in line:
                    tracebacks.append('\n'.join(current_tb))
                    current_tb = []
                    in_traceback = False

        if current_tb:
            tracebacks.append('\n'.join(current_tb))

        return tracebacks

    @staticmethod
    def get_failure_summary(output: str) -> str:
        """Get a concise summary of test failures."""
        parsed = ErrorParser.parse_pytest_output(output)

        summary_parts = []

        if parsed["failed_tests"]:
            summary_parts.append(f"Failed tests: {', '.join(parsed['failed_tests'][:3])}")

        if parsed["error_messages"]:
            summary_parts.append(f"Errors: {'; '.join(parsed['error_messages'][:2])}")

        return '\n'.join(summary_parts) if summary_parts else "Test failure (details not parsed)"


def test_self_correction():
    """Quick test of self-correction loop."""
    print("Self-correction module loaded successfully")
    print("Classes available: SelfCorrectionLoop, CorrectionResult, CorrectionConfig, ErrorParser")

    # Test error parser
    sample_output = """
============================= test session starts ==============================
collected 3 items

test_auth.py::test_login FAILED
test_auth.py::test_logout PASSED

=================================== FAILURES ===================================
__________________________ test_login __________________________

    def test_login():
>       assert login("user@example.com", "pass") == True
E       AssertionError: assert False == True

test_auth.py:15: AssertionError
=========================== short test summary info ============================
FAILED test_auth.py::test_login - AssertionError: assert False == True
========================= 1 failed, 1 passed in 0.12s =========================
    """

    parsed = ErrorParser.parse_pytest_output(sample_output)
    print(f"\nParsed pytest output:")
    print(f"  Passed: {parsed['passed']}")
    print(f"  Failed: {parsed['failed']}")
    print(f"  Failed tests: {parsed['failed_tests']}")
    print(f"  Errors: {parsed['error_messages']}")

    summary = ErrorParser.get_failure_summary(sample_output)
    print(f"\nFailure summary:\n  {summary}")


if __name__ == "__main__":
    test_self_correction()
