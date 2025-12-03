"""
Reproduction test generator for Opus Ensemble.

Generates failing tests that prove the bug exists:
1. Analyze issue description + localized code context
2. Generate test code using LLM
3. Execute against base commit to verify it FAILS
4. Retry if test passes (didn't capture bug)

The key insight: a good reproduction test MUST FAIL on the buggy code.
If it passes, it doesn't capture the bug.
"""

import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from ..api_client import EnsembleAPIClient as APIClient
    from ..docker_executor import DockerExecutor, ExecutionResult
except ImportError:
    from api_client import EnsembleAPIClient as APIClient
    from docker_executor import DockerExecutor, ExecutionResult


# Prompt templates for reproduction test generation
REPRO_TEST_PROMPT = """You are an expert at writing reproduction tests for bugs.

## Issue Description
{issue_description}

## Relevant Code Context
{code_context}

## Your Task
Write a minimal reproduction test that:
1. Demonstrates the bug described in the issue
2. MUST FAIL when run against the buggy code
3. Should PASS after the bug is fixed
4. Is self-contained and can be run with pytest

## Requirements
- Use pytest framework
- Include clear test function names (test_*)
- Add docstring explaining what bug it tests
- Keep it minimal - only test the specific bug
- Include any necessary imports
- If the bug requires specific setup, include that

## Output Format
Return ONLY the Python test code, nothing else.
The code should be complete and runnable.

```python
# Your test code here
```
"""

REFINE_TEST_PROMPT = """The reproduction test you generated passed when it should have FAILED.

A good reproduction test MUST FAIL on the buggy code to prove the bug exists.

## Original Issue
{issue_description}

## Your Previous Test
```python
{previous_test}
```

## Test Output (it passed but should have failed)
{test_output}

## Instructions
Analyze why the test passed and modify it to actually trigger the bug.
Common issues:
- Test isn't hitting the specific code path with the bug
- Test input doesn't match the conditions that trigger the bug
- Assertions aren't checking the right thing

Return ONLY the corrected Python test code.

```python
# Your corrected test code here
```
"""


@dataclass
class ReproductionConfig:
    """Configuration for reproduction test generation."""
    max_retries: int = 3
    test_timeout: int = 60
    parallel_attempts: int = 3  # Generate multiple tests in parallel
    temperature: float = 0.7  # Higher temp for diversity
    max_tokens: int = 2000


@dataclass
class ReproductionResult:
    """Result from reproduction test generation."""
    success: bool
    test_code: Optional[str] = None
    test_file_path: Optional[str] = None
    failure_output: Optional[str] = None  # Output showing test fails
    attempts: int = 0
    error: Optional[str] = None


class ReproductionGenerator:
    """
    Generates reproduction tests that prove a bug exists.

    The key validation: the test MUST FAIL on the base commit (buggy code).
    If it passes, it doesn't actually reproduce the bug.

    Usage:
        generator = ReproductionGenerator(
            api_client=client,
            docker_executor=executor
        )

        result = generator.generate(
            issue_description="Login fails when username contains @",
            code_context="def login(username, password): ...",
            test_cmd="pytest test_repro.py -v"
        )

        if result.success:
            print(f"Generated failing test: {result.test_code}")
    """

    def __init__(
        self,
        api_client: APIClient,
        docker_executor: Optional[DockerExecutor] = None,
        config: Optional[ReproductionConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize reproduction generator.

        Args:
            api_client: Client for LLM API calls
            docker_executor: Executor for running tests (optional for local testing)
            config: Configuration options
            logger: Logger instance
        """
        self.api_client = api_client
        self.docker_executor = docker_executor
        self.config = config or ReproductionConfig()
        self.logger = logger or logging.getLogger(__name__)

    def _extract_code(self, response: str) -> str:
        """Extract Python code from LLM response."""
        # Try to find code block
        code_match = re.search(r'```python\s*(.*?)```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Try plain code block
        code_match = re.search(r'```\s*(.*?)```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Assume entire response is code
        return response.strip()

    def _generate_test(
        self,
        issue_description: str,
        code_context: str,
        attempt: int = 0
    ) -> Optional[str]:
        """
        Generate a reproduction test using the LLM.

        Args:
            issue_description: Description of the bug
            code_context: Relevant code from localization
            attempt: Current attempt number (for temperature scaling)

        Returns:
            Generated test code or None if failed
        """
        prompt = REPRO_TEST_PROMPT.format(
            issue_description=issue_description,
            code_context=code_context
        )

        # Scale temperature based on attempt for diversity
        temperature = min(1.0, self.config.temperature + (attempt * 0.1))

        try:
            response = self.api_client.generate(
                prompt=prompt,
                temperature=temperature,
                max_tokens=self.config.max_tokens
            )
            return self._extract_code(response)
        except Exception as e:
            self.logger.error(f"Failed to generate test: {e}")
            return None

    def _refine_test(
        self,
        issue_description: str,
        previous_test: str,
        test_output: str
    ) -> Optional[str]:
        """
        Refine a test that passed but should have failed.

        Args:
            issue_description: Original issue
            previous_test: The test that incorrectly passed
            test_output: Output from running the test

        Returns:
            Refined test code or None
        """
        prompt = REFINE_TEST_PROMPT.format(
            issue_description=issue_description,
            previous_test=previous_test,
            test_output=test_output
        )

        try:
            response = self.api_client.generate(
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            return self._extract_code(response)
        except Exception as e:
            self.logger.error(f"Failed to refine test: {e}")
            return None

    def _validate_test_syntax(self, test_code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate test code syntax.

        Args:
            test_code: Python test code

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            compile(test_code, '<test>', 'exec')
            return True, None
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

    def _run_test_in_docker(
        self,
        test_code: str,
        test_file_path: str = "test_repro.py",
        test_cmd: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Run test in Docker and check if it fails.

        Args:
            test_code: Python test code
            test_file_path: Where to write the test
            test_cmd: Command to run the test

        Returns:
            Tuple of (test_failed, output)
            - test_failed=True means SUCCESS (we want failure)
        """
        if not self.docker_executor:
            raise RuntimeError("Docker executor required for test validation")

        # Write test file
        write_result = self.docker_executor.write_file(test_file_path, test_code)
        if not write_result.success:
            return False, f"Failed to write test file: {write_result.stderr}"

        # Run test
        test_cmd = test_cmd or f"python -m pytest {test_file_path} -v"
        result = self.docker_executor.execute(
            test_cmd,
            timeout=self.config.test_timeout
        )

        # Test SHOULD fail - so return_code != 0 is success
        test_failed = result.return_code != 0
        output = result.stdout + "\n" + result.stderr

        return test_failed, output

    def _run_test_locally(
        self,
        test_code: str,
        repo_path: str,
        test_file_path: str = "test_repro.py"
    ) -> Tuple[bool, str]:
        """
        Run test locally (fallback when no Docker).

        Args:
            test_code: Python test code
            repo_path: Repository path
            test_file_path: Where to write test

        Returns:
            Tuple of (test_failed, output)
        """
        import subprocess

        full_path = Path(repo_path) / test_file_path
        full_path.write_text(test_code, encoding="utf-8")

        try:
            result = subprocess.run(
                ["python", "-m", "pytest", str(full_path), "-v"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=self.config.test_timeout
            )
            test_failed = result.returncode != 0
            output = result.stdout + "\n" + result.stderr
            return test_failed, output
        except subprocess.TimeoutExpired:
            return False, "Test timed out"
        except Exception as e:
            return False, f"Error running test: {e}"
        finally:
            # Cleanup
            if full_path.exists():
                full_path.unlink()

    def generate(
        self,
        issue_description: str,
        code_context: str,
        test_cmd: Optional[str] = None,
        repo_path: Optional[str] = None
    ) -> ReproductionResult:
        """
        Generate a reproduction test that fails on buggy code.

        Args:
            issue_description: Description of the bug
            code_context: Relevant code from localization
            test_cmd: Command to run the test (for Docker)
            repo_path: Repository path (for local testing)

        Returns:
            ReproductionResult with test code if successful
        """
        attempts = 0
        best_test = None
        best_output = None

        for attempt in range(self.config.max_retries):
            attempts += 1
            self.logger.info(f"Reproduction attempt {attempts}/{self.config.max_retries}")

            # Generate test
            if best_test and best_output:
                # Refine previous test
                test_code = self._refine_test(
                    issue_description,
                    best_test,
                    best_output
                )
            else:
                # Generate new test
                test_code = self._generate_test(
                    issue_description,
                    code_context,
                    attempt
                )

            if not test_code:
                self.logger.warning(f"Attempt {attempts}: No test generated")
                continue

            # Validate syntax
            is_valid, error = self._validate_test_syntax(test_code)
            if not is_valid:
                self.logger.warning(f"Attempt {attempts}: Invalid syntax - {error}")
                continue

            # Run test and check if it fails
            try:
                if self.docker_executor:
                    test_failed, output = self._run_test_in_docker(
                        test_code,
                        test_cmd=test_cmd
                    )
                elif repo_path:
                    test_failed, output = self._run_test_locally(
                        test_code,
                        repo_path
                    )
                else:
                    # Just validate syntax if no execution environment
                    self.logger.warning("No execution environment - returning unvalidated test")
                    return ReproductionResult(
                        success=True,
                        test_code=test_code,
                        test_file_path="test_repro.py",
                        attempts=attempts,
                        error="Test not validated - no Docker or repo_path provided"
                    )

                if test_failed:
                    # Success! Test fails on buggy code
                    self.logger.info(f"Generated failing test on attempt {attempts}")
                    return ReproductionResult(
                        success=True,
                        test_code=test_code,
                        test_file_path="test_repro.py",
                        failure_output=output,
                        attempts=attempts
                    )
                else:
                    # Test passed - need to refine
                    self.logger.warning(f"Attempt {attempts}: Test passed (should have failed)")
                    best_test = test_code
                    best_output = output

            except Exception as e:
                self.logger.error(f"Attempt {attempts}: Error running test - {e}")
                continue

        # All attempts failed
        return ReproductionResult(
            success=False,
            test_code=best_test,  # Return best attempt even if not validated
            attempts=attempts,
            error=f"Failed to generate failing test after {attempts} attempts"
        )

    def generate_parallel(
        self,
        issue_description: str,
        code_context: str,
        test_cmd: Optional[str] = None,
        n_parallel: Optional[int] = None
    ) -> List[ReproductionResult]:
        """
        Generate multiple reproduction tests in parallel.

        Useful for getting diverse test approaches.

        Args:
            issue_description: Description of the bug
            code_context: Relevant code from localization
            test_cmd: Command to run tests
            n_parallel: Number of parallel attempts

        Returns:
            List of ReproductionResult (successful ones first)
        """
        n_parallel = n_parallel or self.config.parallel_attempts
        results = []

        def generate_one(attempt: int) -> Optional[str]:
            """Generate a single test."""
            return self._generate_test(
                issue_description,
                code_context,
                attempt
            )

        # Generate tests in parallel
        with ThreadPoolExecutor(max_workers=n_parallel) as pool:
            futures = [
                pool.submit(generate_one, i)
                for i in range(n_parallel)
            ]

            test_codes = []
            for future in as_completed(futures):
                try:
                    code = future.result()
                    if code:
                        test_codes.append(code)
                except Exception as e:
                    self.logger.error(f"Parallel generation error: {e}")

        # Validate each test (could also parallelize this)
        for test_code in test_codes:
            # Syntax check
            is_valid, error = self._validate_test_syntax(test_code)
            if not is_valid:
                results.append(ReproductionResult(
                    success=False,
                    test_code=test_code,
                    attempts=1,
                    error=f"Syntax error: {error}"
                ))
                continue

            # If we have Docker, validate the test actually fails
            if self.docker_executor:
                try:
                    test_failed, output = self._run_test_in_docker(
                        test_code,
                        test_cmd=test_cmd
                    )
                    results.append(ReproductionResult(
                        success=test_failed,
                        test_code=test_code,
                        test_file_path="test_repro.py",
                        failure_output=output if test_failed else None,
                        attempts=1,
                        error=None if test_failed else "Test passed but should fail"
                    ))
                except Exception as e:
                    results.append(ReproductionResult(
                        success=False,
                        test_code=test_code,
                        attempts=1,
                        error=str(e)
                    ))
            else:
                # Just return the test without validation
                results.append(ReproductionResult(
                    success=True,  # Optimistic - we validated syntax
                    test_code=test_code,
                    test_file_path="test_repro.py",
                    attempts=1,
                    error="Not validated in Docker"
                ))

        # Sort by success (successful first)
        results.sort(key=lambda r: (not r.success, r.attempts))
        return results


def test_reproduction_generator():
    """Quick test of reproduction generator."""
    from ..api_client import APIClient
    from ..config import EnsembleConfig

    # Mock API client for testing
    class MockAPIClient:
        def generate(self, prompt: str, **kwargs) -> str:
            return '''```python
import pytest

def test_login_with_at_symbol():
    """Test that login handles @ in username."""
    from myapp.auth import login

    # This should work but currently fails
    result = login("user@example.com", "password123")
    assert result.success, "Login should succeed with @ in username"
```'''

    generator = ReproductionGenerator(
        api_client=MockAPIClient(),  # type: ignore
        docker_executor=None,
        config=ReproductionConfig(max_retries=1)
    )

    result = generator.generate(
        issue_description="Login fails when username contains @",
        code_context="def login(username, password): ...",
    )

    print(f"Success: {result.success}")
    print(f"Attempts: {result.attempts}")
    print(f"Test code:\n{result.test_code}")


if __name__ == "__main__":
    test_reproduction_generator()
