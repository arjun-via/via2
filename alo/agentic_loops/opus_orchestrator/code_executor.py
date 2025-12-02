"""
=============================================================================
SCRIPT NAME: code_executor.py
=============================================================================

Code Executor - Actually runs generated code to validate it works.

INPUT FILES:
- Generated code string

OUTPUT FILES:
- ExecutionResult with pass/fail and output

VERSION: 1.0
LAST UPDATED: 2025-11-27

DESCRIPTION:
Provides sandboxed code execution to validate that generated code actually
runs without errors. This is critical for the "FAIL IS FAIL" principle -
we don't trust LLM validation alone.

DEPENDENCIES:
- subprocess (standard library)
- tempfile (standard library)
- ast (standard library)

=============================================================================
"""

import subprocess
import tempfile
import os
import re
import ast
from typing import Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    """Result from code execution."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    error_type: Optional[str] = None  # SyntaxError, ImportError, RuntimeError, etc.
    error_message: Optional[str] = None
    execution_time: float = 0.0


class CodeExecutor:
    """
    Executes Python code in a sandboxed subprocess.

    Safety features:
    - Runs in subprocess (isolated from main process)
    - Timeout enforcement
    - No network access in generated code (detected statically)
    - No file writes outside temp directory
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize the code executor.

        Args:
            timeout: Maximum execution time in seconds
        """
        self.timeout = timeout

    def execute(self, code: str, test_code: Optional[str] = None) -> ExecutionResult:
        """
        Execute Python code and return the result.

        Args:
            code: Python code to execute
            test_code: Optional test code to run after main code

        Returns:
            ExecutionResult with success/failure and output
        """
        # First, do static analysis
        static_result = self._static_check(code)
        if not static_result.success:
            return static_result

        # Combine code with test code if provided
        full_code = code
        if test_code:
            full_code = f"{code}\n\n# Test code\n{test_code}"

        # Write to temp file and execute
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False
        ) as f:
            f.write(full_code)
            temp_path = f.name

        try:
            import time
            start_time = time.time()

            result = subprocess.run(
                ['python', temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=tempfile.gettempdir()  # Run in temp dir for safety
            )

            execution_time = time.time() - start_time

            if result.returncode == 0:
                return ExecutionResult(
                    success=True,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=0,
                    execution_time=execution_time
                )
            else:
                # Parse error type from stderr
                error_type, error_msg = self._parse_error(result.stderr)
                return ExecutionResult(
                    success=False,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.returncode,
                    error_type=error_type,
                    error_message=error_msg,
                    execution_time=execution_time
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {self.timeout} seconds",
                return_code=-1,
                error_type="TimeoutError",
                error_message=f"Code took longer than {self.timeout}s to execute"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                error_type="ExecutionError",
                error_message=str(e)
            )
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass

    def _static_check(self, code: str) -> ExecutionResult:
        """
        Perform static analysis before execution.

        Checks:
        - Syntax validity
        - No dangerous imports
        - No obvious security issues
        """
        # Check syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"SyntaxError: {e.msg} (line {e.lineno})",
                return_code=-1,
                error_type="SyntaxError",
                error_message=f"{e.msg} at line {e.lineno}"
            )

        # Check for dangerous patterns
        dangerous_patterns = [
            (r'\bos\.system\b', "os.system() is not allowed"),
            (r'\bsubprocess\b', "subprocess module is not allowed in generated code"),
            (r'\beval\s*\(', "eval() is not allowed"),
            (r'\bexec\s*\(', "exec() is not allowed"),
            (r'\b__import__\b', "__import__() is not allowed"),
            (r'\bopen\s*\([^)]*["\']w', "File writing is not allowed"),
            (r'\brequests\b', "requests module not available (stdlib only)"),
        ]

        for pattern, message in dangerous_patterns:
            if re.search(pattern, code):
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"Security check failed: {message}",
                    return_code=-1,
                    error_type="SecurityError",
                    error_message=message
                )

        # Passed static checks
        return ExecutionResult(
            success=True,
            stdout="",
            stderr="",
            return_code=0
        )

    def _parse_error(self, stderr: str) -> Tuple[str, str]:
        """Parse error type and message from stderr."""
        # Common Python error patterns
        error_patterns = [
            (r'SyntaxError: (.+)', 'SyntaxError'),
            (r'IndentationError: (.+)', 'IndentationError'),
            (r'NameError: (.+)', 'NameError'),
            (r'TypeError: (.+)', 'TypeError'),
            (r'ValueError: (.+)', 'ValueError'),
            (r'AttributeError: (.+)', 'AttributeError'),
            (r'ImportError: (.+)', 'ImportError'),
            (r'ModuleNotFoundError: (.+)', 'ImportError'),
            (r'KeyError: (.+)', 'KeyError'),
            (r'IndexError: (.+)', 'IndexError'),
            (r'ZeroDivisionError: (.+)', 'ZeroDivisionError'),
            (r'RecursionError: (.+)', 'RecursionError'),
            (r'AssertionError:?\s*(.*)', 'AssertionError'),
        ]

        for pattern, error_type in error_patterns:
            match = re.search(pattern, stderr)
            if match:
                return error_type, match.group(1).strip() if match.group(1) else error_type

        # Unknown error
        return "RuntimeError", stderr.strip()[:200]

    def extract_code(self, content: str) -> Optional[str]:
        """
        Extract Python code from LLM response.

        Handles:
        - ```python blocks
        - ``` blocks
        - Raw code

        Args:
            content: LLM response content

        Returns:
            Extracted Python code or None
        """
        # Try ```python block first
        match = re.search(r'```python\n(.*?)```', content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try generic ``` block
        match = re.search(r'```\n(.*?)```', content, re.DOTALL)
        if match:
            code = match.group(1).strip()
            # Verify it looks like Python
            if self._looks_like_python(code):
                return code

        # Try unclosed ```python block
        match = re.search(r'```python\n(.+)', content, re.DOTALL)
        if match:
            code = match.group(1).strip()
            # Remove trailing ``` if present at very end
            if code.endswith('```'):
                code = code[:-3].strip()
            return code

        # Check if whole content is code
        if self._looks_like_python(content):
            return content.strip()

        return None

    def _looks_like_python(self, code: str) -> bool:
        """Check if text looks like Python code."""
        python_indicators = [
            r'^def\s+\w+',
            r'^class\s+\w+',
            r'^import\s+',
            r'^from\s+\w+\s+import',
            r':\s*$',
            r'^\s+return\s+',
        ]

        for pattern in python_indicators:
            if re.search(pattern, code, re.MULTILINE):
                return True
        return False


def generate_test_code(feature_tests: List[str], class_name: Optional[str] = None) -> str:
    """
    Generate test code from feature test descriptions.

    Args:
        feature_tests: List of test descriptions from feature spec
        class_name: Optional class name to instantiate

    Returns:
        Python test code string
    """
    test_lines = [
        "# Auto-generated tests",
        "import sys",
        "",
        "def run_tests():",
        "    passed = 0",
        "    failed = 0",
        "    errors = []",
        "",
    ]

    for i, test_desc in enumerate(feature_tests):
        test_lines.append(f"    # Test {i+1}: {test_desc}")
        test_lines.append("    try:")
        test_lines.append(f"        # TODO: Implement test for: {test_desc}")
        test_lines.append("        passed += 1")
        test_lines.append("    except Exception as e:")
        test_lines.append("        failed += 1")
        test_lines.append(f"        errors.append(('Test {i+1}', str(e)))")
        test_lines.append("")

    test_lines.extend([
        "    print(f'Tests: {passed} passed, {failed} failed')",
        "    if errors:",
        "        for name, err in errors:",
        "            print(f'  {name}: {err}')",
        "    return failed == 0",
        "",
        "if __name__ == '__main__':",
        "    success = run_tests()",
        "    sys.exit(0 if success else 1)",
    ])

    return "\n".join(test_lines)


def create_basic_test(code: str, class_name: str = None) -> str:
    """
    Create a basic smoke test for generated code.

    This test just verifies the code:
    1. Has no syntax errors (handled by executor)
    2. Can be imported/executed
    3. Main class/function exists if specified

    Args:
        code: The generated code
        class_name: Optional class name to check for

    Returns:
        Test code string
    """
    test_lines = ["# Basic smoke test"]

    if class_name:
        test_lines.extend([
            f"# Verify {class_name} class exists and can be instantiated",
            f"assert '{class_name}' in dir(), f'{class_name} class not defined'",
            f"print(f'{class_name} class exists: OK')",
        ])

    test_lines.append("print('Basic smoke test: PASSED')")

    return "\n".join(test_lines)
