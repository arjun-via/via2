"""
=============================================================================
SCRIPT NAME: docker_executor.py
=============================================================================

Docker Executor for Opus Ensemble - Container pool management for parallel
patch verification.

INPUT FILES:
- SWE-bench instance metadata (image name, working directory)

OUTPUT FILES:
- Command execution results (stdout, stderr, return code)

VERSION: 1.0
LAST UPDATED: 2025-12-02

DESCRIPTION:
Provides Docker container pool management for parallel patch verification.
Each patch candidate can be tested in its own container for isolation.

Key features:
- Container pool for parallel verification
- Repository snapshot per container
- Safe command execution with timeout
- Cleanup on completion

DEPENDENCIES:
- subprocess (standard library)
- uuid (standard library)

=============================================================================
"""

import logging
import os
import shlex
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any

# Ensure parent directory is in path for imports
_this_dir = Path(__file__).parent.resolve()
if str(_this_dir) not in sys.path:
    sys.path.insert(0, str(_this_dir))

from config import get_config


@dataclass
class ExecutionResult:
    """Result from executing a command in Docker."""
    output: str
    return_code: int
    timed_out: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.return_code == 0 and not self.timed_out and self.error is None


@dataclass
class ContainerInfo:
    """Information about a running container."""
    container_id: str
    container_name: str
    image: str
    cwd: str


class DockerExecutor:
    """
    Executes bash commands in a Docker container for SWE-bench evaluation.

    Usage:
        with DockerExecutor(image="python:3.11-slim") as executor:
            result = executor.execute("ls -la")
            print(result.output)
    """

    def __init__(
        self,
        image: str,
        cwd: str = "/testbed",
        timeout: int = 60,
        memory_limit: str = "4g",
        cpu_limit: float = 2.0,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize Docker executor.

        Args:
            image: Docker image name
            cwd: Working directory inside container
            timeout: Default timeout for command execution
            memory_limit: Memory limit for container
            cpu_limit: CPU limit for container
            logger: Optional logger instance
        """
        self.image = image
        self.cwd = cwd
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.logger = logger or logging.getLogger("opus_ensemble.docker")

        self.container_id: Optional[str] = None
        self.container_name: Optional[str] = None
        self._started = False

    def _check_image_exists(self) -> bool:
        """Check if the Docker image exists locally."""
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", self.image],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def _pull_image(self, timeout: int = 600) -> bool:
        """
        Pull the Docker image if not available locally.
        
        Args:
            timeout: Maximum time to wait for pull (default 10 min)
            
        Returns:
            True if image is available (pulled or already existed)
        """
        if self._check_image_exists():
            self.logger.info(f"Image {self.image} already exists locally")
            return True
        
        self.logger.info(f"Pulling image {self.image} (this may take several minutes)...")
        try:
            result = subprocess.run(
                ["docker", "pull", self.image],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode == 0:
                self.logger.info(f"Successfully pulled {self.image}")
                return True
            else:
                self.logger.error(f"Failed to pull image: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            self.logger.error(f"Image pull timed out after {timeout}s")
            return False
        except Exception as e:
            self.logger.error(f"Error pulling image: {e}")
            return False

    def start(self, pull_if_missing: bool = True, pull_timeout: int = 600) -> bool:
        """
        Start the Docker container.

        Args:
            pull_if_missing: If True, attempt to pull image if not available locally
            pull_timeout: Timeout for image pull in seconds (default 10 min)

        Returns:
            True if container started successfully, False otherwise
        """
        if self._started:
            return True

        # Check/pull image first if requested
        if pull_if_missing:
            if not self._pull_image(timeout=pull_timeout):
                self.logger.error(f"Image {self.image} not available and pull failed")
                return False

        self.container_name = f"opus-ensemble-{uuid.uuid4().hex[:8]}"

        cmd = [
            "docker", "run",
            "-d",  # Detached mode
            "--name", self.container_name,
            "-w", self.cwd,
            "--rm",  # Remove on exit
            f"--memory={self.memory_limit}",
            f"--cpus={self.cpu_limit}",
            self.image,
            "sleep", "2h"  # Container stays alive for 2 hours
        ]

        self.logger.debug(f"Starting container: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # Container start should be fast once image exists
                check=True
            )
            self.container_id = result.stdout.strip()
            self._started = True
            self.logger.info(f"Started container {self.container_name}")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to start container: {e.stderr}")
            return False
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout starting container")
            return False

    def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a bash command in the container.

        Args:
            command: Bash command to execute
            timeout: Optional timeout override
            cwd: Optional working directory override

        Returns:
            ExecutionResult with output and return code
        """
        if not self._started:
            if not self.start():
                return ExecutionResult(
                    output="",
                    return_code=-1,
                    error="Failed to start container"
                )

        timeout = timeout or self.timeout
        cwd = cwd or self.cwd

        cmd = [
            "docker", "exec",
            "-w", cwd,
            self.container_id,
            "bash", "-lc", command
        ]

        self.logger.debug(f"Executing: {command[:100]}...")

        try:
            result = subprocess.run(
                cmd,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            return ExecutionResult(
                output=result.stdout,
                return_code=result.returncode
            )

        except subprocess.TimeoutExpired as e:
            output = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
            return ExecutionResult(
                output=output + f"\n\n[TIMEOUT after {timeout}s]",
                return_code=-1,
                timed_out=True,
                error=f"Command timed out after {timeout}s"
            )
        except Exception as e:
            return ExecutionResult(
                output="",
                return_code=-1,
                error=str(e)
            )

    def read_file(self, path: str) -> ExecutionResult:
        """Read a file from the container."""
        return self.execute(f"cat {shlex.quote(path)}")

    def write_file(self, path: str, content: str) -> ExecutionResult:
        """Write content to a file in the container."""
        escaped_content = content.replace("'", "'\\''")
        command = f"cat > {shlex.quote(path)} << 'OPUS_EOF'\n{content}\nOPUS_EOF"
        return self.execute(command)

    def apply_patch(self, patch: str) -> ExecutionResult:
        """
        Apply a patch in the container.

        Handles various patch formats:
        - SEARCH/REPLACE format (new)
        - Standard unified diff
        - Patches with /testbed/ prefix (strips it)
        """
        import re

        # Check if it's SEARCH/REPLACE format
        if "<<<<<<< SEARCH" in patch and ">>>>>>> REPLACE" in patch:
            return self._apply_search_replace_patch(patch)

        # Handle unified diff format
        # Fix common patch issues:
        # 1. Strip /testbed/ prefix from paths
        fixed_patch = re.sub(r'^(---|\+\+\+) a/testbed/', r'\1 a/', patch, flags=re.MULTILINE)
        fixed_patch = re.sub(r'^(---|\+\+\+) b/testbed/', r'\1 b/', fixed_patch, flags=re.MULTILINE)

        # 2. Also handle testbed/ without leading slash
        fixed_patch = re.sub(r'^(---|\+\+\+) a/testbed/', r'\1 a/', fixed_patch, flags=re.MULTILINE)
        fixed_patch = re.sub(r'^(---|\+\+\+) b/testbed/', r'\1 b/', fixed_patch, flags=re.MULTILINE)

        write_result = self.write_file("/tmp/opus_patch.diff", fixed_patch)
        if write_result.return_code != 0:
            return write_result

        # Try standard git apply first
        result = self.execute("git apply /tmp/opus_patch.diff")
        if result.success:
            return result

        # If that fails, try with --3way (3-way merge, more tolerant of context)
        result2 = self.execute("git apply --3way /tmp/opus_patch.diff")
        if result2.success:
            return result2

        # Try with --unidiff-zero (handles empty @@ lines)
        result3 = self.execute("git apply --unidiff-zero /tmp/opus_patch.diff")
        if result3.success:
            return result3

        # Try patch command with fuzz factor (very lenient with context)
        result4 = self.execute("patch -p1 --fuzz=3 < /tmp/opus_patch.diff")
        if result4.success:
            return result4

        # Return the original error
        return result

    def _apply_search_replace_patch(self, patch: str) -> ExecutionResult:
        """
        Apply a SEARCH/REPLACE format patch.

        Supported formats:
        1. 3-section with explicit path:
           <<<<<<< SEARCH
           path/to/file.py
           =======
           search text
           =======
           replace text
           >>>>>>> REPLACE

        2. 2-section (path on first line of search):
           <<<<<<< SEARCH
           path/to/file.py
           search text
           =======
           replace text
           >>>>>>> REPLACE
        """
        import re

        blocks = []

        # Pattern 1: 3-section format (path / search / replace separated by =======)
        block_pattern_3section = r"<<<<<<< SEARCH\s*\n([^\n=]+\.py)\n=======\n(.*?)\n=======\n(.*?)>>>>>>> REPLACE"
        matches_3sec = re.findall(block_pattern_3section, patch, re.DOTALL)
        for path, search, replace in matches_3sec:
            blocks.append((path.strip(), search.strip(), replace.strip()))

        # Pattern 2: 2-section format (search / replace separated by single =======)
        # The path might be embedded in the first line of search
        if not blocks:
            block_pattern_2section = r"<<<<<<< SEARCH\s*\n(.*?)\n=======\n(.*?)>>>>>>> REPLACE"
            matches_2sec = re.findall(block_pattern_2section, patch, re.DOTALL)
            for search_block, replace in matches_2sec:
                search_lines = search_block.strip().split('\n')
                # Check if first line looks like a file path
                first_line = search_lines[0].strip() if search_lines else ""
                if first_line.endswith('.py') and '/' in first_line and len(first_line) < 200:
                    # First line is likely a path
                    filepath = first_line
                    search_text = '\n'.join(search_lines[1:]).strip()
                else:
                    # No path - will need to search for file
                    filepath = ""
                    search_text = search_block.strip()
                blocks.append((filepath, search_text, replace.strip()))

        if not blocks:
            return ExecutionResult(
                output="No valid SEARCH/REPLACE blocks found in patch",
                return_code=1,
                error="Invalid patch format"
            )

        errors = []
        successes = 0

        for filepath, search_text, replace_text in blocks:
            # Handle paths - strip /testbed/ prefix if present
            if filepath.startswith('/testbed/'):
                filepath = filepath[len('/testbed/'):]
            elif filepath.startswith('testbed/'):
                filepath = filepath[len('testbed/'):]

            # If no path provided, try to find the file by searching
            if not filepath:
                # Search for a file containing the search text
                find_result = self._find_file_with_content(search_text)
                if find_result:
                    filepath = find_result
                    self.logger.info(f"Inferred file path: {filepath}")
                else:
                    errors.append(f"No file path provided and could not find file containing search text")
                    continue

            # Make path absolute
            full_path = f"/testbed/{filepath}"

            # Read the file
            read_result = self.read_file(full_path)
            if not read_result.success:
                errors.append(f"Cannot read {filepath}: {read_result.output}")
                continue

            file_content = read_result.output

            # Try to find and replace the search text using multiple strategies
            applied = False

            # Strategy 1: Exact match
            if search_text in file_content:
                new_content = file_content.replace(search_text, replace_text, 1)
                write_result = self.write_file(full_path, new_content)
                if write_result.success:
                    successes += 1
                    self.logger.info(f"Successfully applied change to {filepath}")
                    applied = True
                else:
                    errors.append(f"Cannot write {filepath}: {write_result.output}")
                    continue

            # Strategy 2: Strip trailing whitespace from each line
            if not applied:
                search_lines = [line.rstrip() for line in search_text.split('\n')]
                content_lines = [line.rstrip() for line in file_content.split('\n')]
                search_stripped = '\n'.join(search_lines)
                content_stripped = '\n'.join(content_lines)

                if search_stripped in content_stripped:
                    new_content = content_stripped.replace(search_stripped, replace_text.strip(), 1)
                    write_result = self.write_file(full_path, new_content)
                    if write_result.success:
                        successes += 1
                        self.logger.info(f"Successfully applied change to {filepath} (whitespace-stripped)")
                        applied = True

            # Strategy 3: Find best matching block using difflib SequenceMatcher
            if not applied:
                from difflib import SequenceMatcher

                # Get the first unique line from search text as anchor
                search_lines = search_text.strip().split('\n')
                content_lines = file_content.split('\n')

                # Try to find the function/class definition line
                anchor_line = None
                for line in search_lines:
                    if line.strip().startswith('def ') or line.strip().startswith('class '):
                        anchor_line = line.strip()
                        break

                if anchor_line:
                    # Find lines in content that match this definition
                    best_match_idx = -1
                    best_match_score = 0

                    for i, content_line in enumerate(content_lines):
                        if anchor_line in content_line or content_line.strip() == anchor_line:
                            # Found the function/class definition
                            # Now try to match the whole block
                            block_start = i
                            block_end = min(i + len(search_lines) + 5, len(content_lines))  # +5 for flexibility
                            candidate_block = '\n'.join(content_lines[block_start:block_end])

                            score = SequenceMatcher(None, search_text.strip(), candidate_block.strip()).ratio()
                            if score > best_match_score and score > 0.7:  # 70% similarity threshold
                                best_match_score = score
                                best_match_idx = block_start

                    if best_match_idx >= 0:
                        # Found a good match - replace the exact number of lines
                        block_to_replace = '\n'.join(content_lines[best_match_idx:best_match_idx + len(search_lines)])

                        # Try direct replacement with the identified block
                        if block_to_replace in file_content:
                            new_content = file_content.replace(block_to_replace, replace_text.strip(), 1)
                            write_result = self.write_file(full_path, new_content)
                            if write_result.success:
                                successes += 1
                                self.logger.info(f"Successfully applied change to {filepath} (fuzzy-matched, score: {best_match_score:.2f})")
                                applied = True

            # Strategy 4: Try line-by-line matching for simple single-line changes
            if not applied:
                search_lines = search_text.strip().split('\n')
                if len(search_lines) <= 3:
                    # For small patches, try to find the key line
                    for search_line in search_lines:
                        if search_line.strip() and not search_line.strip().startswith('#'):
                            # Non-empty, non-comment line
                            search_line_stripped = search_line.strip()
                            for i, content_line in enumerate(content_lines):
                                if content_line.strip() == search_line_stripped:
                                    # Found matching line - replace it
                                    original_indent = len(content_line) - len(content_line.lstrip())
                                    # Apply same indent to replacement
                                    replace_lines = replace_text.strip().split('\n')
                                    indented_replace = []
                                    for rline in replace_lines:
                                        if rline.strip():
                                            indented_replace.append(' ' * original_indent + rline.strip())
                                        else:
                                            indented_replace.append(rline)

                                    content_lines[i] = '\n'.join(indented_replace) if len(indented_replace) > 1 else indented_replace[0]
                                    new_content = '\n'.join(content_lines)
                                    write_result = self.write_file(full_path, new_content)
                                    if write_result.success:
                                        successes += 1
                                        self.logger.info(f"Successfully applied change to {filepath} (line-match)")
                                        applied = True
                                    break
                            if applied:
                                break

            if not applied:
                errors.append(f"Search text not found in {filepath} (tried exact, whitespace-stripped, fuzzy, line-match)")

        if successes > 0:
            return ExecutionResult(
                output=f"Applied {successes}/{len(blocks)} changes",
                return_code=0
            )
        else:
            return ExecutionResult(
                output="Failed to apply changes: " + "; ".join(errors),
                return_code=1,
                error="; ".join(errors)
            )

    def _find_file_with_content(self, search_text: str) -> Optional[str]:
        """
        Search for a file containing the given text.

        Args:
            search_text: Text to search for

        Returns:
            Relative file path if found, None otherwise
        """
        # Get first line of search text for grep
        first_line = search_text.strip().split('\n')[0].strip()
        if not first_line or len(first_line) < 5:
            return None

        # Escape special chars for grep
        import shlex
        escaped_line = first_line.replace("'", "'\\''")

        # Search for files containing the first line
        result = self.execute(
            f"grep -rl '{escaped_line}' /testbed --include='*.py' 2>/dev/null | head -5",
            timeout=30
        )

        if result.success and result.output.strip():
            files = result.output.strip().split('\n')
            for f in files:
                f = f.strip()
                if f.startswith('/testbed/'):
                    return f[len('/testbed/'):]
                return f

        return None

    def get_diff(self) -> ExecutionResult:
        """Get the current git diff."""
        return self.execute("git add -A && git diff --cached")

    def run_tests(self, test_cmd: str, timeout: int = 300) -> ExecutionResult:
        """
        Run tests with extended timeout.

        Args:
            test_cmd: Test command (e.g., "pytest tests/test_foo.py")
            timeout: Timeout for test execution (default 5 min)
        """
        return self.execute(test_cmd, timeout=timeout)

    def reset_repo(self) -> ExecutionResult:
        """Reset the repository to clean state."""
        return self.execute("git checkout . && git clean -fd")

    def cleanup(self):
        """Stop and remove the container."""
        if self.container_id:
            self.logger.debug(f"Cleaning up container {self.container_name}")
            cmd = f"docker stop {self.container_id} >/dev/null 2>&1 || docker rm -f {self.container_id} >/dev/null 2>&1"
            subprocess.run(cmd, shell=True, capture_output=True)
            self.container_id = None
            self._started = False

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
        return False

    def __del__(self):
        """Cleanup on garbage collection."""
        try:
            self.cleanup()
        except Exception:
            pass


class ContainerPool:
    """
    Pool of Docker containers for parallel patch verification.

    Usage:
        pool = ContainerPool(image="python:3.11-slim", pool_size=10)
        pool.start()

        # Run patches in parallel
        results = pool.run_parallel(patches, verify_fn)

        pool.cleanup()
    """

    def __init__(
        self,
        image: str,
        pool_size: int = 10,
        cwd: str = "/testbed",
        timeout: int = 60,
        memory_limit: str = "4g",
        cpu_limit: float = 2.0,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize container pool.

        Args:
            image: Docker image name
            pool_size: Number of containers in the pool
            cwd: Working directory inside containers
            timeout: Default command timeout
            memory_limit: Memory limit per container
            cpu_limit: CPU limit per container
            logger: Optional logger instance
        """
        self.image = image
        self.pool_size = pool_size
        self.cwd = cwd
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.logger = logger or logging.getLogger("opus_ensemble.pool")

        self.executors: List[DockerExecutor] = []
        self._started = False

    def start(self) -> int:
        """
        Start all containers in the pool.

        Returns:
            Number of containers successfully started
        """
        if self._started:
            return len(self.executors)

        self.logger.info(f"Starting container pool with {self.pool_size} containers...")

        started = 0
        for i in range(self.pool_size):
            executor = DockerExecutor(
                image=self.image,
                cwd=self.cwd,
                timeout=self.timeout,
                memory_limit=self.memory_limit,
                cpu_limit=self.cpu_limit,
                logger=self.logger
            )
            if executor.start():
                self.executors.append(executor)
                started += 1
            else:
                self.logger.warning(f"Failed to start container {i+1}")

        self._started = True
        self.logger.info(f"Container pool ready: {started}/{self.pool_size} containers")
        return started

    def run_parallel(
        self,
        items: List[Any],
        verify_fn: Callable[[DockerExecutor, Any], Any],
        max_workers: Optional[int] = None
    ) -> List[Any]:
        """
        Run verification function on items in parallel using container pool.

        Args:
            items: List of items to process
            verify_fn: Function(executor, item) -> result
            max_workers: Max parallel workers (default: pool size)

        Returns:
            List of results in same order as items
        """
        if not self._started:
            self.start()

        max_workers = max_workers or len(self.executors)
        results = [None] * len(items)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_idx = {}

            for idx, item in enumerate(items):
                # Round-robin assignment to executors
                executor = self.executors[idx % len(self.executors)]
                future = pool.submit(verify_fn, executor, item)
                future_to_idx[future] = idx

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    self.logger.error(f"Error processing item {idx}: {e}")
                    results[idx] = None

        return results

    def cleanup(self):
        """Stop all containers in the pool."""
        self.logger.info("Cleaning up container pool...")
        for executor in self.executors:
            executor.cleanup()
        self.executors = []
        self._started = False

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
        return False


def get_swebench_image(instance_id: str, use_epoch: bool = True) -> str:
    """
    Get the Docker image name for a SWE-bench instance.

    Args:
        instance_id: SWE-bench instance ID (e.g., "django__django-12345")
        use_epoch: If True, use Epoch AI optimized images (10x smaller, recommended)

    Returns:
        Docker image name

    Epoch AI images (RECOMMENDED):
        - 10x smaller than official images (30 GB total for 500 vs 189 GB)
        - Pre-built and ready to pull
        - All 500 SWE-bench Verified images available
        - Format: ghcr.io/epoch-research/swe-bench.eval.x86_64.{instance_id}:latest

    Official SWE-bench images (legacy):
        - Format: swebench/sweb.eval.x86_64.{repo}_{version}_{issue}:latest

    Example:
        django__django-13023 -> ghcr.io/epoch-research/swe-bench.eval.x86_64.django__django-13023:latest
    """
    if use_epoch:
        # Epoch AI optimized images - 10x smaller, all 500 verified available
        # Format: ghcr.io/epoch-research/swe-bench.eval.x86_64.{instance_id}:latest
        return f"ghcr.io/epoch-research/swe-bench.eval.x86_64.{instance_id}:latest"
    else:
        # Legacy official SWE-bench images
        parts = instance_id.split("__")
        if len(parts) == 2:
            repo = parts[0]
            issue = parts[1]
            version = "1776"
            return f"swebench/sweb.eval.x86_64.{repo}_{version}_{issue}:latest"
        else:
            normalized = instance_id.replace("__", "_").replace("-", "_")
            return f"swebench/sweb.eval.x86_64.{normalized}:latest"


def test_docker():
    """Quick test of Docker executor."""
    logging.basicConfig(level=logging.DEBUG)

    print("Testing DockerExecutor...")
    with DockerExecutor(image="python:3.11-slim", cwd="/tmp") as executor:
        # Test basic execution
        result = executor.execute("echo 'Hello World'")
        print(f"  Echo output: {result.output.strip()}")
        assert result.success

        # Test file operations
        executor.write_file("/tmp/test.py", "print('Hello from Python')")
        result = executor.execute("python /tmp/test.py")
        print(f"  Python output: {result.output.strip()}")
        assert result.success

    print("DockerExecutor tests passed!")


def test_pool():
    """Quick test of container pool."""
    logging.basicConfig(level=logging.DEBUG)

    print("Testing ContainerPool...")
    with ContainerPool(image="python:3.11-slim", pool_size=3, cwd="/tmp") as pool:
        items = [f"echo 'Item {i}'" for i in range(5)]

        def run_cmd(executor: DockerExecutor, cmd: str) -> str:
            result = executor.execute(cmd)
            return result.output.strip()

        results = pool.run_parallel(items, run_cmd)
        print(f"  Results: {results}")
        assert len(results) == 5

    print("ContainerPool tests passed!")


if __name__ == "__main__":
    test_docker()
    print()
    test_pool()
