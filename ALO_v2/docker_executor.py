"""
=============================================================================
ALO v2.0 Docker Executor
=============================================================================

Executes commands in SWE-bench Docker containers.

FEATURES:
- Container lifecycle management (start, stop, cleanup)
- Command execution with timeout
- File read/write operations
- Patch application and extraction
=============================================================================
"""

import subprocess
import time
import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ExecutionResult:
    """Result of a Docker command execution"""
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


class DockerExecutor:
    """Executes commands in SWE-bench Docker containers"""

    def __init__(self, instance_id: str, timeout: int = 120):
        """
        Initialize Docker executor for a SWE-bench instance.

        Args:
            instance_id: SWE-bench instance ID (e.g., "django__django-11292")
            timeout: Default command timeout in seconds
        """
        self.instance_id = instance_id
        self.timeout = timeout
        self.container_name = f"swebench_{instance_id.replace('/', '_').replace(':', '_')}"
        self.image_name = self._get_image_name(instance_id)
        self.container_running = False

    def _get_image_name(self, instance_id: str) -> str:
        """Get the SWE-bench Docker image name for an instance"""
        # SWE-bench image naming: swebench/sweb.eval.x86_64.{repo}_1776_{repo}-{issue}:latest
        # e.g., django__django-11292 -> swebench/sweb.eval.x86_64.django_1776_django-11292:latest
        # Replace __ with _1776_
        image_suffix = instance_id.replace("__", "_1776_")
        return f"swebench/sweb.eval.x86_64.{image_suffix}:latest"

    def start_container(self) -> bool:
        """Start the Docker container for this instance"""
        try:
            # Check if container already exists
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", f"name={self.container_name}", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=30
            )

            if self.container_name in result.stdout:
                # Container exists, start it if not running
                subprocess.run(
                    ["docker", "start", self.container_name],
                    capture_output=True, text=True, timeout=30
                )
            else:
                # Create and start new container
                subprocess.run(
                    [
                        "docker", "run", "-d",
                        "--name", self.container_name,
                        "--workdir", "/testbed",
                        self.image_name,
                        "tail", "-f", "/dev/null"  # Keep container running
                    ],
                    capture_output=True, text=True, timeout=60, check=True
                )

            self.container_running = True

            # Install the package in development mode (needed for tests)
            self._setup_environment()

            return True

        except subprocess.CalledProcessError as e:
            print(f"Failed to start container: {e.stderr}")
            return False
        except subprocess.TimeoutExpired:
            print("Timeout starting container")
            return False

    def _setup_environment(self):
        """Set up the development environment in the container"""
        # Install package in editable mode
        self.execute("pip install -e /testbed -q 2>/dev/null || true", timeout=60)

    def stop_container(self):
        """Stop and remove the container"""
        try:
            subprocess.run(
                ["docker", "stop", self.container_name],
                capture_output=True, text=True, timeout=30
            )
            subprocess.run(
                ["docker", "rm", self.container_name],
                capture_output=True, text=True, timeout=30
            )
            self.container_running = False
        except Exception:
            pass  # Best effort cleanup

    def execute(self, command: str, timeout: Optional[int] = None) -> ExecutionResult:
        """
        Execute a command in the container.

        Args:
            command: Shell command to execute
            timeout: Command timeout in seconds (uses default if not specified)

        Returns:
            ExecutionResult with stdout, stderr, exit_code, timed_out
        """
        timeout = timeout or self.timeout

        try:
            result = subprocess.run(
                ["docker", "exec", self.container_name, "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return ExecutionResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                timed_out=False
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-1,
                timed_out=True
            )
        except Exception as e:
            return ExecutionResult(
                stdout="",
                stderr=str(e),
                exit_code=-1,
                timed_out=False
            )

    def read_file(self, path: str) -> Optional[str]:
        """Read a file from the container"""
        result = self.execute(f"cat '{path}'")
        if result.exit_code == 0:
            return result.stdout
        return None

    def write_file(self, path: str, content: str) -> bool:
        """Write content to a file in the container"""
        # Use heredoc to handle special characters
        escaped_content = content.replace("'", "'\"'\"'")
        result = self.execute(f"cat > '{path}' << 'EOFMARKER'\n{content}\nEOFMARKER")
        return result.exit_code == 0

    def apply_patch(self, patch: str) -> Tuple[bool, str]:
        """
        Apply a git patch to the repository.

        Args:
            patch: The unified diff patch content

        Returns:
            Tuple of (success, message)
        """
        # Write patch to temp file
        self.execute("rm -f /tmp/fix.patch")
        if not self.write_file("/tmp/fix.patch", patch):
            return False, "Failed to write patch file"

        # Reset any previous changes
        self.execute("cd /testbed && git checkout -- .")

        # Apply the patch
        result = self.execute("cd /testbed && git apply /tmp/fix.patch")

        if result.exit_code == 0:
            return True, "Patch applied successfully"
        else:
            # Try with --reject to see what failed
            result = self.execute("cd /testbed && git apply --reject /tmp/fix.patch 2>&1")
            return False, f"Patch failed: {result.stdout}\n{result.stderr}"

    def run_tests(self, test_cmd: str, timeout: int = 300) -> Tuple[bool, str]:
        """
        Run tests in the container.

        Args:
            test_cmd: Test command to run
            timeout: Test timeout in seconds

        Returns:
            Tuple of (passed, output)
        """
        result = self.execute(f"cd /testbed && {test_cmd}", timeout=timeout)

        # Check for common test pass indicators
        output = result.stdout + result.stderr
        passed = result.exit_code == 0

        return passed, output

    def get_diff(self) -> str:
        """Get the current git diff in the container"""
        result = self.execute("cd /testbed && git diff")
        return result.stdout if result.exit_code == 0 else ""

    def list_files(self, path: str = ".") -> list:
        """List files in a directory"""
        result = self.execute(f"cd /testbed && find {path} -type f -name '*.py' | head -100")
        if result.exit_code == 0:
            return [f.strip() for f in result.stdout.split("\n") if f.strip()]
        return []

    def __enter__(self):
        """Context manager entry - start container"""
        self.start_container()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop container"""
        self.stop_container()
        return False


def test_executor():
    """Test the Docker executor with a sample instance"""
    instance_id = "django__django-11292"

    print(f"Testing DockerExecutor with {instance_id}")

    with DockerExecutor(instance_id) as executor:
        # Test basic command
        result = executor.execute("pwd")
        print(f"PWD: {result.stdout.strip()}")

        # Test file listing
        files = executor.list_files("django/core")
        print(f"Found {len(files)} Python files in django/core")

        # Test file reading
        content = executor.read_file("/testbed/setup.py")
        if content:
            print(f"Read setup.py: {len(content)} bytes")

        # Test git diff (should be empty initially)
        diff = executor.get_diff()
        print(f"Initial diff: {len(diff)} bytes")

    print("DockerExecutor test complete!")


if __name__ == "__main__":
    test_executor()
