"""Code-based objective evaluators for AI-generated Python code."""
import ast
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CodeEvalResult:
    """Results from code-based evaluation."""

    # Syntax validation
    syntax_valid: bool
    syntax_error: Optional[str] = None

    # Execution testing
    executes: bool = False
    execution_error: Optional[str] = None
    error_type: Optional[str] = None

    # Pattern matching
    has_required_patterns: bool = False
    missing_patterns: List[str] = None
    found_patterns: List[str] = None

    # Test execution (if applicable)
    tests_passed: int = 0
    tests_failed: int = 0
    test_output: Optional[str] = None

    def __post_init__(self):
        if self.missing_patterns is None:
            self.missing_patterns = []
        if self.found_patterns is None:
            self.found_patterns = []


class CodeEvaluator:
    """Evaluates AI-generated code with objective, deterministic checks."""

    # Required patterns for each prompt type
    PROMPT_PATTERNS = {
        "rate_limiter": [
            r"(threading\.Lock|Lock\(\)|RLock)",  # Thread safety
            r"time\.(time|monotonic)",  # Time tracking
        ],
        "lru_cache": [
            r"(OrderedDict|collections\.OrderedDict)",  # LRU implementation
            r"(threading\.Lock|Lock\(\)|RLock)",  # Thread safety
        ],
        "distributed_lock": [
            r"redis",  # Redis usage
            r"(acquire|lock)",  # Lock acquisition
            r"(expire|ttl)",  # Lock expiration
        ],
        "async_task_queue": [
            r"(asyncio|async def)",  # Async support
            r"(priority|heapq)",  # Priority queue
        ],
        "byzantine_consensus": [
            r"(consensus|vote|quorum)",  # Consensus algorithm
        ],
        "compiler_parser": [
            r"(parse|parser|ast)",  # Parsing
            r"(if|else|while)",  # Control flow
        ],
        "database_btree": [
            r"(class.*Node|BTreeNode)",  # Node class
            r"(split|merge)",  # B-tree operations
        ],
        "timeseries_anomaly": [
            r"(mean|std|zscore)",  # Statistical methods
            r"(anomaly|outlier)",  # Anomaly detection
        ],
        "graph_cycle_detection": [
            r"(dfs|depth.first|tarjan)",  # Graph algorithms
            r"(cycle|scc|component)",  # Cycle detection
        ],
        "regex_engine": [
            r"(nfa|state|thompson)",  # NFA/Thompson construction
            r"(match|compile)",  # Regex matching
        ],
    }

    def __init__(self, timeout: int = 10):
        """Initialize evaluator.

        Args:
            timeout: Maximum seconds for code execution
        """
        self.timeout = timeout

    def extract_code_blocks(self, text: str) -> List[str]:
        """Extract Python code blocks from text.

        Args:
            text: Text potentially containing code blocks

        Returns:
            List of extracted code strings
        """
        blocks = []

        # Try to extract markdown code blocks first (```python, ```diff, or ```patch)
        pattern = r"```(?:python|diff|patch)?\s*\n(.*?)```"
        markdown_blocks = re.findall(pattern, text, re.DOTALL)

        for block in markdown_blocks:
            # If it's a diff/patch block, extract only the added lines
            if re.search(r"^(@@ |--- |diff )", block, re.MULTILINE):
                # For multi-file patches, split by file boundaries
                file_sections = re.split(r'(?=^--- )', block, flags=re.MULTILINE)

                for section in file_sections:
                    if not section.strip():
                        continue
                    # Extract lines starting with + (but not +++)
                    code_lines = []
                    for line in section.split('\n'):
                        if line.startswith('+') and not line.startswith('+++'):
                            # Remove the + prefix
                            code_lines.append(line[1:])
                    if code_lines:
                        blocks.append('\n'.join(code_lines))
            else:
                # Regular code block
                blocks.append(block)

        if blocks:
            return blocks

        # If no markdown blocks, treat entire text as code if it looks like code
        # (has def/class/import statements)
        if re.search(r"^\s*(def|class|import|from)\s", text, re.MULTILINE):
            return [text]

        return []

    def check_syntax(self, code: str) -> tuple[bool, Optional[str]]:
        """Check if code is syntactically valid Python.

        Args:
            code: Python code string

        Returns:
            (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"Parse error: {str(e)}"

    def execute_code(self, code: str) -> tuple[bool, Optional[str], Optional[str]]:
        """Attempt to execute code in a sandboxed environment.

        Args:
            code: Python code string

        Returns:
            (executed_successfully, error_message, error_type)
        """
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Run in subprocess with timeout
            result = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0:
                return True, None, None
            else:
                # Parse error type from stderr
                error_type = self._classify_error(result.stderr)
                return False, result.stderr, error_type

        except subprocess.TimeoutExpired:
            return False, f"Execution timed out after {self.timeout}s", "TimeoutError"
        except Exception as e:
            return False, str(e), type(e).__name__
        finally:
            # Cleanup
            Path(temp_path).unlink(missing_ok=True)

    def _classify_error(self, stderr: str) -> str:
        """Classify error type from stderr output."""
        error_patterns = {
            "ImportError": r"ImportError|ModuleNotFoundError",
            "NameError": r"NameError",
            "TypeError": r"TypeError",
            "AttributeError": r"AttributeError",
            "ValueError": r"ValueError",
            "RuntimeError": r"RuntimeError",
            "IndentationError": r"IndentationError",
        }

        for error_type, pattern in error_patterns.items():
            if re.search(pattern, stderr):
                return error_type

        return "UnknownError"

    def check_patterns(self, code: str, prompt_id: str) -> tuple[bool, List[str], List[str]]:
        """Check if code contains required patterns for the prompt type.

        Args:
            code: Python code string
            prompt_id: Identifier for the prompt (e.g., "rate_limiter")

        Returns:
            (has_all_patterns, found_patterns, missing_patterns)
        """
        required_patterns = self.PROMPT_PATTERNS.get(prompt_id, [])

        if not required_patterns:
            # No patterns defined for this prompt
            return True, [], []

        found = []
        missing = []

        for pattern in required_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                found.append(pattern)
            else:
                missing.append(pattern)

        has_all = len(missing) == 0
        return has_all, found, missing

    def evaluate(self, output: str, prompt_id: str = None) -> CodeEvalResult:
        """Run full code evaluation suite.

        Args:
            output: AI-generated output (may contain code blocks)
            prompt_id: Optional identifier to check prompt-specific patterns

        Returns:
            CodeEvalResult with all evaluation metrics
        """
        result = CodeEvalResult(syntax_valid=False)

        # Extract code blocks
        code_blocks = self.extract_code_blocks(output)

        if not code_blocks:
            result.syntax_error = "No code blocks found in output"
            return result

        # Use the largest code block (most likely to be the main implementation)
        code = max(code_blocks, key=len)

        # Step 1: Syntax validation
        syntax_valid, syntax_error = self.check_syntax(code)
        result.syntax_valid = syntax_valid
        result.syntax_error = syntax_error

        if not syntax_valid:
            return result

        # Step 2: Execution testing
        executes, exec_error, error_type = self.execute_code(code)
        result.executes = executes
        result.execution_error = exec_error
        result.error_type = error_type

        # Step 3: Pattern matching (if prompt_id provided)
        if prompt_id:
            has_patterns, found, missing = self.check_patterns(code, prompt_id)
            result.has_required_patterns = has_patterns
            result.found_patterns = found
            result.missing_patterns = missing

        return result

    def evaluate_batch(self, outputs: List[tuple[str, str]]) -> List[CodeEvalResult]:
        """Evaluate multiple outputs.

        Args:
            outputs: List of (output, prompt_id) tuples

        Returns:
            List of CodeEvalResult objects
        """
        return [self.evaluate(output, prompt_id) for output, prompt_id in outputs]
