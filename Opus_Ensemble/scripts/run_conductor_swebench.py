#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_conductor_swebench.py
=============================================================================

Run Opus-Conductor on SWE-bench Verified with Docker-based test verification.

This compares:
1. Opus-Conductor (multi-stage with validation)
2. Opus baseline (single-shot)

Using proper SWE-bench Docker containers for verification.

USAGE:
    # Run on 25 random tasks
    python scripts/run_conductor_swebench.py --num 25 --random

    # Run specific tasks
    python scripts/run_conductor_swebench.py --num 10 --start 0

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import argparse
import json
import logging
import random
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from conductor import OpusConductor
from docker_executor import DockerExecutor, get_swebench_image, ExecutionResult


@dataclass
class SWEBenchTask:
    """A SWE-bench task."""
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    hints_text: str = ""
    fail_to_pass: List[str] = None
    pass_to_pass: List[str] = None

    def __post_init__(self):
        self.fail_to_pass = self.fail_to_pass or []
        self.pass_to_pass = self.pass_to_pass or []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SWEBenchTask":
        """Create from HuggingFace/SWE-bench format."""
        fail_to_pass = data.get("FAIL_TO_PASS", data.get("fail_to_pass", []))
        if isinstance(fail_to_pass, str):
            try:
                fail_to_pass = json.loads(fail_to_pass)
            except:
                fail_to_pass = [fail_to_pass] if fail_to_pass else []

        pass_to_pass = data.get("PASS_TO_PASS", data.get("pass_to_pass", []))
        if isinstance(pass_to_pass, str):
            try:
                pass_to_pass = json.loads(pass_to_pass)
            except:
                pass_to_pass = [pass_to_pass] if pass_to_pass else []

        return cls(
            instance_id=data["instance_id"],
            repo=data.get("repo", ""),
            base_commit=data.get("base_commit", ""),
            problem_statement=data.get("problem_statement", ""),
            hints_text=data.get("hints_text", ""),
            fail_to_pass=fail_to_pass,
            pass_to_pass=pass_to_pass,
        )

    def get_test_cmd(self) -> str:
        """Get pytest command for FAIL_TO_PASS tests."""
        if self.fail_to_pass:
            tests = ' '.join(self.fail_to_pass)
            return f"python -m pytest {tests} -xvs"
        return "python -m pytest -xvs"


@dataclass
class TaskResult:
    """Result for one task."""
    instance_id: str
    method: str  # "conductor" or "opus_baseline"
    success: bool
    patch: Optional[str] = None
    test_passed: bool = False
    test_output: str = ""
    cost: float = 0.0
    time: float = 0.0
    error: Optional[str] = None


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )


def load_swebench_verified() -> List[SWEBenchTask]:
    """Load SWE-bench Verified from HuggingFace."""
    try:
        from datasets import load_dataset
        ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")

        tasks = []
        for item in ds:
            tasks.append(SWEBenchTask.from_dict(dict(item)))

        logging.info(f"Loaded {len(tasks)} tasks from SWE-bench Verified")
        return tasks

    except ImportError:
        logging.error("Install datasets: pip install datasets")
        sys.exit(1)


def get_code_context(task: SWEBenchTask, docker_executor: DockerExecutor) -> str:
    """
    Get relevant code context from Docker container.

    Reads FAIL_TO_PASS test files and uses grep to find related source files.
    """
    import re

    context_parts = []

    # Read FAIL_TO_PASS test files
    test_files_read = set()
    for test_path in task.fail_to_pass:
        if '::' in test_path:
            file_path = test_path.split('::')[0]
        else:
            file_path = test_path

        if not file_path.startswith('/'):
            file_path = f"/testbed/{file_path}"

        if file_path not in test_files_read:
            result = docker_executor.read_file(file_path)
            if result.success and result.output:
                test_files_read.add(file_path)
                content = result.output[:15000]
                context_parts.append(f"### TEST FILE (must pass): {file_path}\n```python\n{content}\n```")
                logging.debug(f"Read test file: {file_path} ({len(content)} chars)")

    # Extract keywords from problem statement
    problem = task.problem_statement
    identifiers = re.findall(r'\b([a-z_][a-z0-9_]+)\b', problem.lower())
    stopwords = {'the', 'a', 'an', 'is', 'are', 'in', 'on', 'to', 'for', 'of', 'and', 'or', 'not',
                 'this', 'that', 'it', 'as', 'be', 'have', 'has', 'with', 'from', 'but', 'if',
                 'should', 'would', 'could', 'can', 'will', 'do', 'does', 'bug', 'fix', 'issue'}
    keywords = [w for w in identifiers if w not in stopwords and len(w) > 2]

    class_names = re.findall(r'\b([A-Z][a-zA-Z0-9]+)\b', problem)
    keywords.extend([c.lower() for c in class_names])
    keywords = list(set(keywords))[:5]

    # Find relevant source files via grep
    found_files = set()
    for keyword in keywords:
        result = docker_executor.execute(
            f"grep -rl '{keyword}' /testbed --include='*.py' 2>/dev/null | head -10",
            timeout=30
        )
        if result.success and result.output.strip():
            for line in result.output.strip().split('\n'):
                if line.strip() and '/tests/' not in line and 'test_' not in line.split('/')[-1]:
                    found_files.add(line.strip())

    # Read top source files
    found_files = sorted(list(found_files), key=len)[:5]
    for filepath in found_files:
        result = docker_executor.read_file(filepath)
        if result.success and result.output:
            content = result.output[:10000]
            context_parts.append(f"### Source File: {filepath}\n```python\n{content}\n```")

    return "\n\n".join(context_parts)


def apply_and_test_patch(
    patch: str,
    task: SWEBenchTask,
    docker_executor: DockerExecutor
) -> tuple:
    """
    Apply patch and run tests in Docker.

    Returns (passed, output)
    """
    if not patch:
        return False, "No patch provided"

    # Apply patch
    result = docker_executor.apply_patch(patch)
    if not result.success:
        return False, f"Failed to apply patch: {result.output}"

    # Run tests
    test_cmd = task.get_test_cmd()
    result = docker_executor.execute(test_cmd, timeout=300)

    passed = result.success and ("passed" in result.output.lower() or
                                  "1 passed" in result.output or
                                  "PASSED" in result.output)

    return passed, result.output[:2000]


def run_conductor(
    task: SWEBenchTask,
    conductor: OpusConductor,
    docker_executor: DockerExecutor
) -> TaskResult:
    """Run task through Opus-Conductor."""
    logging.info(f"  [CONDUCTOR] Running: {task.instance_id}")
    start_time = time.time()

    try:
        # Get code context from Docker
        code_context = get_code_context(task, docker_executor)

        # Build enhanced task description
        enhanced_task = f"""## Issue
{task.problem_statement}

## Hints
{task.hints_text}

## Code Context
{code_context}

## Requirements
- Generate a patch in unified diff format
- The patch must make the FAIL_TO_PASS tests pass
- Test command: {task.get_test_cmd()}
"""

        # Run Conductor
        result = conductor.run(task=enhanced_task)
        elapsed = time.time() - start_time

        patch = result.final_code or ""

        # Apply and test in Docker
        if patch:
            test_passed, test_output = apply_and_test_patch(patch, task, docker_executor)
        else:
            test_passed, test_output = False, "No patch generated"

        return TaskResult(
            instance_id=task.instance_id,
            method="conductor",
            success=test_passed,
            patch=patch,
            test_passed=test_passed,
            test_output=test_output[:500],
            cost=result.total_cost,
            time=elapsed,
        )

    except Exception as e:
        logging.error(f"Conductor error: {e}")
        return TaskResult(
            instance_id=task.instance_id,
            method="conductor",
            success=False,
            error=str(e),
            time=time.time() - start_time,
        )


def run_opus_baseline(
    task: SWEBenchTask,
    client,
    docker_executor: DockerExecutor
) -> TaskResult:
    """Run task with single Opus call."""
    logging.info(f"  [OPUS] Running: {task.instance_id}")
    start_time = time.time()

    try:
        # Get code context from Docker
        code_context = get_code_context(task, docker_executor)

        prompt = f"""Fix this issue and provide a patch in unified diff format.

## Issue
{task.problem_statement}

## Hints
{task.hints_text}

## Code Context
{code_context}

## Output Format
Provide ONLY the patch in unified diff format (starting with ---).
The patch must make these tests pass: {task.fail_to_pass}"""

        system = """You are an expert software engineer. Generate a minimal, correct patch.
Output ONLY the unified diff patch, no explanations."""

        response = client.complete(
            messages=[{"role": "user", "content": prompt}],
            system=system,
        )
        elapsed = time.time() - start_time

        # Extract patch from response
        import re
        patch_match = re.search(r'(---.*?)(?=```|$)', response.content, re.DOTALL)
        if patch_match:
            patch = patch_match.group(1).strip()
        else:
            patch = response.content

        # Apply and test in Docker
        if patch:
            test_passed, test_output = apply_and_test_patch(patch, task, docker_executor)
        else:
            test_passed, test_output = False, "No patch extracted"

        return TaskResult(
            instance_id=task.instance_id,
            method="opus_baseline",
            success=test_passed,
            patch=patch,
            test_passed=test_passed,
            test_output=test_output[:500],
            cost=response.cost,
            time=elapsed,
        )

    except Exception as e:
        logging.error(f"Opus baseline error: {e}")
        return TaskResult(
            instance_id=task.instance_id,
            method="opus_baseline",
            success=False,
            error=str(e),
            time=time.time() - start_time,
        )


def main():
    parser = argparse.ArgumentParser(description="Run Opus-Conductor vs baseline on SWE-bench")
    parser.add_argument("--num", type=int, default=25, help="Number of tasks")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--random", action="store_true", help="Random selection")
    parser.add_argument("--output", "-o", type=str, default="conductor_swebench.jsonl")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("=" * 70)
    print("OPUS-CONDUCTOR vs OPUS BASELINE - SWE-bench Verified")
    print("=" * 70)
    print()

    # Load tasks
    tasks = load_swebench_verified()

    if args.random:
        tasks = random.sample(tasks, min(args.num, len(tasks)))
    else:
        tasks = tasks[args.start:args.start + args.num]

    print(f"Running {len(tasks)} tasks...")
    print("-" * 70)

    # Initialize Conductor
    conductor = OpusConductor.from_config("config/conductor_config.yaml")
    opus_client = conductor.supervisor_client

    conductor_results = []
    baseline_results = []

    for i, task in enumerate(tasks):
        print(f"\n[{i+1}/{len(tasks)}] Task: {task.instance_id}")
        print(f"  {task.problem_statement[:60]}...")

        # Get Docker image for this task
        docker_image = get_swebench_image(task.instance_id)
        print(f"  Docker: {docker_image}")

        # Create Docker executor
        docker_executor = DockerExecutor(
            image=docker_image,
            cwd="/testbed",
            timeout=300,
        )

        try:
            if not docker_executor.start():
                print(f"  ERROR: Failed to start Docker container")
                continue

            # Run Conductor
            c_result = run_conductor(task, conductor, docker_executor)
            conductor_results.append(c_result)
            print(f"  [CONDUCTOR] test={'PASS' if c_result.test_passed else 'FAIL'}, "
                  f"cost=${c_result.cost:.4f}, time={c_result.time:.1f}s")

            # Reset container for baseline
            docker_executor.execute("git checkout .", timeout=60)
            docker_executor.execute("git clean -fd", timeout=60)

            # Run baseline
            b_result = run_opus_baseline(task, opus_client, docker_executor)
            baseline_results.append(b_result)
            print(f"  [OPUS]      test={'PASS' if b_result.test_passed else 'FAIL'}, "
                  f"cost=${b_result.cost:.4f}, time={b_result.time:.1f}s")

            # Save incremental results
            with open(args.output, 'a') as f:
                f.write(json.dumps({"conductor": asdict(c_result), "baseline": asdict(b_result)}) + '\n')

        finally:
            docker_executor.cleanup()

    # Summary
    c_passed = sum(1 for r in conductor_results if r.test_passed)
    b_passed = sum(1 for r in baseline_results if r.test_passed)

    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print()
    print(f"{'Metric':<25} {'Conductor':<20} {'Opus Baseline':<20}")
    print("-" * 70)
    print(f"{'Tasks Solved':<25} {c_passed}/{len(conductor_results):<20} {b_passed}/{len(baseline_results):<20}")
    print(f"{'Solve Rate':<25} {100*c_passed/len(conductor_results):.1f}%{'':<17} {100*b_passed/len(baseline_results):.1f}%")
    print(f"{'Total Cost':<25} ${sum(r.cost for r in conductor_results):.2f}{'':<16} ${sum(r.cost for r in baseline_results):.2f}")
    print(f"{'Total Time':<25} {sum(r.time for r in conductor_results)/60:.1f}min{'':<14} {sum(r.time for r in baseline_results)/60:.1f}min")
    print()

    # Save full results
    summary_file = args.output.replace('.jsonl', '_summary.json')
    summary = {
        "timestamp": datetime.now().isoformat(),
        "num_tasks": len(tasks),
        "conductor_solved": c_passed,
        "baseline_solved": b_passed,
        "conductor_rate": c_passed / len(conductor_results) if conductor_results else 0,
        "baseline_rate": b_passed / len(baseline_results) if baseline_results else 0,
    }
    Path(summary_file).write_text(json.dumps(summary, indent=2))
    print(f"Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
