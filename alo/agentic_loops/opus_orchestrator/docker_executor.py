"""
=============================================================================
SCRIPT NAME: docker_executor.py
=============================================================================

Docker Executor for SWE-bench - Manages Docker containers for code execution.

INPUT FILES:
- SWE-bench instance metadata (image name, working directory)

OUTPUT FILES:
- Command execution results (stdout, stderr, return code)

VERSION: 1.0
LAST UPDATED: 2025-11-28

DESCRIPTION:
Provides Docker container management for executing commands in SWE-bench
evaluation environments. Supports the agentic loop pattern where an LLM
can execute bash commands and observe outputs.

Based on mini-swe-agent's DockerEnvironment pattern.

DEPENDENCIES:
- subprocess (standard library)
- uuid (standard library)

=============================================================================
"""

import logging
import os
import shlex
import subprocess
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class DockerConfig:
    """Configuration for Docker executor."""
    image: str
    cwd: str = "/testbed"
    env: Dict[str, str] = field(default_factory=dict)
    timeout: int = 60
    container_timeout: str = "2h"
    pull_timeout: int = 300  # SWE-bench images can be large


@dataclass
class ExecutionResult:
    """Result from executing a command in Docker."""
    output: str
    return_code: int
    timed_out: bool = False
    error: Optional[str] = None


class DockerExecutor:
    """
    Executes bash commands in a Docker container for SWE-bench evaluation.

    Usage:
        executor = DockerExecutor(image="swebench/sweb.eval.x86_64.django_1776:latest")
        result = executor.execute("ls -la")
        print(result.output)
        executor.cleanup()
    """

    def __init__(
        self,
        image: str,
        cwd: str = "/testbed",
        timeout: int = 60,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize Docker executor.

        Args:
            image: Docker image name (e.g., swebench/sweb.eval.x86_64.django_1776:latest)
            cwd: Working directory inside container
            timeout: Default timeout for command execution
            logger: Optional logger instance
        """
        self.config = DockerConfig(image=image, cwd=cwd, timeout=timeout)
        self.logger = logger or logging.getLogger("opus.docker")
        self.container_id: Optional[str] = None
        self.container_name: Optional[str] = None
        self._started = False

    def start(self) -> bool:
        """
        Start the Docker container.

        Returns:
            True if container started successfully, False otherwise
        """
        if self._started:
            return True

        self.container_name = f"opus-agent-{uuid.uuid4().hex[:8]}"

        cmd = [
            "docker", "run",
            "-d",  # Detached mode
            "--name", self.container_name,
            "-w", self.config.cwd,
            "--rm",  # Remove on exit
            self.config.image,
            "sleep", self.config.container_timeout
        ]

        self.logger.debug(f"Starting container: {shlex.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.pull_timeout,  # Allow time for image pull
                check=True
            )
            self.container_id = result.stdout.strip()
            self._started = True
            self.logger.info(f"Started container {self.container_name} (ID: {self.container_id[:12]})")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to start container: {e.stderr}")
            return False
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout starting container (image pull took too long)")
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

        timeout = timeout or self.config.timeout
        cwd = cwd or self.config.cwd

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
                stderr=subprocess.STDOUT  # Combine stderr into stdout
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
        # Use heredoc to handle multi-line content
        escaped_content = content.replace("'", "'\\''")
        command = f"cat > {shlex.quote(path)} << 'OPUS_EOF'\n{content}\nOPUS_EOF"
        return self.execute(command)

    def apply_patch(self, patch: str) -> ExecutionResult:
        """Apply a git patch in the container."""
        # Write patch to temp file and apply
        write_result = self.write_file("/tmp/opus_patch.diff", patch)
        if write_result.return_code != 0:
            return write_result

        return self.execute("git apply /tmp/opus_patch.diff")

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

    def cleanup(self):
        """Stop and remove the container."""
        if self.container_id:
            self.logger.debug(f"Cleaning up container {self.container_name}")
            # Run cleanup in background to not block
            cmd = f"(timeout 60 docker stop {self.container_id} || docker rm -f {self.container_id}) >/dev/null 2>&1 &"
            subprocess.Popen(cmd, shell=True)
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
        self.cleanup()


def get_swebench_image(instance_id: str) -> str:
    """
    Get the Docker image name for a SWE-bench instance.

    Args:
        instance_id: SWE-bench instance ID (e.g., "django__django-12345")

    Returns:
        Docker image name
    """
    # Parse instance ID to get repo and version info
    parts = instance_id.split("__")
    if len(parts) != 2:
        raise ValueError(f"Invalid instance ID format: {instance_id}")

    repo_owner, repo_issue = parts[0], parts[1]
    repo_name, issue_num = repo_issue.rsplit("-", 1)

    # SWE-bench image naming convention
    # Format: swebench/sweb.eval.x86_64.{repo_owner}_{version}_{repo}-{issue}:latest
    # But actually each instance has its own image based on the instance ID

    # The actual format from swebench harness
    return f"docker.io/swebench/sweb.eval.x86_64.{instance_id.replace('__', '_').replace('-', '_')}:latest"


# Convenience function for quick testing
def test_docker_executor():
    """Quick test of Docker executor."""
    logging.basicConfig(level=logging.DEBUG)

    # Test with a simple ubuntu image
    with DockerExecutor(image="python:3.11-slim", cwd="/tmp") as executor:
        # Test basic execution
        result = executor.execute("echo 'Hello World'")
        print(f"Output: {result.output}")
        print(f"Return code: {result.return_code}")

        # Test file operations
        executor.write_file("/tmp/test.py", "print('Hello from Python')")
        result = executor.execute("python /tmp/test.py")
        print(f"Python output: {result.output}")


if __name__ == "__main__":
    test_docker_executor()
