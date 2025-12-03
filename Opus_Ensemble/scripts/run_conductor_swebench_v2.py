#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_conductor_swebench_v2.py
=============================================================================

Run Opus-Conductor on SWE-bench with Docker-based iterative editing.

This version integrates Conductor's multi-stage validation with an iterative
Docker loop that edits files directly (not patch generation).

Conductor Flow for SWE-bench:
1. Planning Stage: Opus analyzes problem, identifies files to modify
2. Context Stage: Read relevant files from Docker container
3. Engineering Stage: Iterative EDIT loop in Docker (sed/python edits)
4. Review Stage: Opus validates the changes
5. Execution Stage: Run tests to verify

VERSION: 2.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import argparse
import json
import logging
import random
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))

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
        if self.fail_to_pass:
            tests = ' '.join(self.fail_to_pass)
            return f"python -m pytest {tests} -xvs"
        return "python -m pytest -xvs"


@dataclass
class TaskResult:
    instance_id: str
    method: str
    success: bool
    patch: Optional[str] = None
    test_passed: bool = False
    test_output: str = ""
    cost: float = 0.0
    time: float = 0.0
    steps: int = 0
    error: Optional[str] = None


# System prompt for Conductor's iterative Docker loop
CONDUCTOR_SYSTEM_PROMPT = r'''You are Opus-Conductor, an expert software engineer fixing bugs in Python repositories.

CONDUCTOR PROTOCOL:
You operate in a multi-stage validation loop. For each step:
1. THINK: Analyze what you need to do next
2. ACT: Execute ONE bash command
3. OBSERVE: Wait for real output (DO NOT hallucinate!)
4. VALIDATE: Check if progress was made

CRITICAL RULES:
1. Write ONLY ONE bash command per response in a ```bash block
2. WAIT for actual output - NEVER imagine/hallucinate command results
3. EDIT actual source files (not test files) to fix the bug
4. DO NOT submit until you've verified your changes work

WORKFLOW:
Step 1: Find source files related to the bug
```bash
find . -name "*.py" -path "*/src/*" | head -20
```

Step 2: Read the relevant source file
```bash
cat ./path/to/source.py
```

Step 3: EDIT the source file (use sed or python)
```bash
sed -i 's/buggy_code/fixed_code/g' ./path/to/source.py
```

Step 4: Verify your edit
```bash
cat ./path/to/source.py | grep -A5 "fixed_code"
```

Step 5: Check git diff shows SOURCE file changes
```bash
git add -A && git diff --cached
```

Step 6: Say SUBMIT when diff shows source changes

EDITING TECHNIQUES:
- Small: sed -i 's/old/new/g' file.py
- Multi-line: python -c "..." to read, modify, write
- Full rewrite: cat > file.py << 'EOF' ... EOF

FORBIDDEN:
- DO NOT create test_*.py files as your fix
- DO NOT hallucinate command output
- DO NOT submit without source file edits
'''


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )


def load_swebench_verified() -> List[SWEBenchTask]:
    try:
        from datasets import load_dataset
        ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
        tasks = [SWEBenchTask.from_dict(dict(item)) for item in ds]
        logging.info(f"Loaded {len(tasks)} tasks from SWE-bench Verified")
        return tasks
    except ImportError:
        logging.error("Install datasets: pip install datasets")
        sys.exit(1)


def parse_bash_command(response: str) -> Optional[str]:
    """Extract bash command from response."""
    match = re.search(r'```bash\n(.*?)```', response, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r'```\n(.*?)```', response, re.DOTALL)
    if match:
        cmd = match.group(1).strip()
        if cmd.startswith(('find ', 'grep ', 'cat ', 'ls ', 'sed ', 'python', 'git ')):
            return cmd
    return None


def truncate_output(output: str, max_chars: int = 15000) -> str:
    if len(output) <= max_chars:
        return output
    half = max_chars // 2
    return output[:half] + f"\n[...truncated {len(output)-max_chars} chars...]\n" + output[-half:]


def detect_hallucination(response: str) -> bool:
    """Check if model is hallucinating output."""
    patterns = [
        r'```bash\n.*?```\s*\n\s*(Output|Result|stdout)\s*[:=]',
        r'```bash\n.*?```\s*\n\s*```\s*\n',
    ]
    for pattern in patterns:
        if re.search(pattern, response, re.DOTALL | re.IGNORECASE):
            return True
    bash_blocks = re.findall(r'```bash\n.*?```', response, re.DOTALL)
    return len(bash_blocks) > 1


class ConductorSWEBench:
    """
    Conductor for SWE-bench with Docker-based iterative editing.

    Implements the Conductor pattern:
    - Opus supervises each stage
    - Multi-stage validation (planning → context → engineering → review)
    - Iterative editing in Docker container
    """

    def __init__(
        self,
        docker_executor: DockerExecutor,
        max_steps: int = 30,
        logger: Optional[logging.Logger] = None,
    ):
        self.docker = docker_executor
        self.max_steps = max_steps
        self.logger = logger or logging.getLogger(__name__)

        # Initialize Anthropic client for Opus
        self.client = anthropic.Anthropic()
        self.model = "claude-opus-4-5-20250514"

        self.total_cost = 0.0
        self.total_tokens = 0

    def _log(self, msg: str):
        self.logger.info(f"[CONDUCTOR] {msg}")

    def _call_opus(self, messages: List[Dict], system: str) -> tuple:
        """Call Opus and track cost."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,
        )

        # Track costs (Opus pricing: $15/M input, $75/M output)
        input_cost = response.usage.input_tokens * 15 / 1_000_000
        output_cost = response.usage.output_tokens * 75 / 1_000_000
        self.total_cost += input_cost + output_cost
        self.total_tokens += response.usage.input_tokens + response.usage.output_tokens

        return response.content[0].text, response.usage

    def run(self, task: SWEBenchTask) -> TaskResult:
        """Run Conductor on a SWE-bench task."""
        self._log(f"Starting task: {task.instance_id}")
        start_time = time.time()

        # Build initial prompt with problem context
        initial_prompt = f"""## Bug Report
{task.problem_statement}

## Hints
{task.hints_text if task.hints_text else "No hints provided"}

## Tests That Must Pass
{task.fail_to_pass}

## Your Task
Fix this bug by editing the source files. The fix should make the failing tests pass.

Start by exploring the codebase to understand the bug and identify which files to modify.
"""

        messages = [{"role": "user", "content": initial_prompt}]
        steps = []

        for step_num in range(self.max_steps):
            # STAGE: Engineering - get next action from Opus
            self._log(f"Step {step_num + 1}/{self.max_steps}")

            try:
                response_text, usage = self._call_opus(messages, CONDUCTOR_SYSTEM_PROMPT)
            except Exception as e:
                self._log(f"Opus API error: {e}")
                return TaskResult(
                    instance_id=task.instance_id,
                    method="conductor_v2",
                    success=False,
                    error=str(e),
                    cost=self.total_cost,
                    time=time.time() - start_time,
                    steps=step_num,
                )

            # Check for SUBMIT signal
            if "SUBMIT" in response_text.upper():
                self._log("Received SUBMIT signal")
                break

            # Detect hallucination
            if detect_hallucination(response_text):
                self._log("WARNING: Detected possible hallucination, correcting...")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({
                    "role": "user",
                    "content": "STOP! You appear to be hallucinating command output. "
                               "Write ONLY ONE bash command and wait for the actual result."
                })
                continue

            # Parse bash command
            command = parse_bash_command(response_text)
            if not command:
                self._log("No command found in response")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({
                    "role": "user",
                    "content": "Please provide a bash command to execute. "
                               "Use a ```bash code block."
                })
                continue

            # STAGE: Execution - run command in Docker
            self._log(f"Executing: {command[:80]}...")
            result = self.docker.execute(command, timeout=60)

            output = truncate_output(result.output) if result.output else "(no output)"

            # Build observation for next iteration
            observation = f"Command executed. Return code: {result.return_code}\n\nOutput:\n{output}"

            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": observation})

            steps.append({
                "step": step_num + 1,
                "command": command,
                "return_code": result.return_code,
                "output_preview": output[:200],
            })

        # Get final patch
        diff_result = self.docker.execute("git add -A && git diff --cached")
        patch = diff_result.output if diff_result.success else ""

        # STAGE: Review - validate patch has source changes
        has_source_changes = self._validate_patch(patch)

        if not has_source_changes:
            self._log("WARNING: No source file changes detected")

        # STAGE: Test execution
        test_cmd = task.get_test_cmd()
        self._log(f"Running tests: {test_cmd}")
        test_result = self.docker.execute(test_cmd, timeout=300)

        test_passed = (
            test_result.success and
            ("passed" in test_result.output.lower() or "PASSED" in test_result.output)
        )

        elapsed = time.time() - start_time

        return TaskResult(
            instance_id=task.instance_id,
            method="conductor_v2",
            success=test_passed and has_source_changes,
            patch=patch,
            test_passed=test_passed,
            test_output=test_result.output[:1000] if test_result.output else "",
            cost=self.total_cost,
            time=elapsed,
            steps=len(steps),
        )

    def _validate_patch(self, patch: str) -> bool:
        """Validate patch has source file changes (not just test files)."""
        if not patch:
            return False

        # Check for source file changes (not test files)
        source_patterns = [
            r'^diff --git a/.*\.py',  # Any .py file
            r'^\+\+\+ b/.*\.py',       # Added/modified .py
        ]

        test_only = True
        for line in patch.split('\n'):
            for pattern in source_patterns:
                if re.match(pattern, line):
                    # Check it's not a test file
                    if 'test_' not in line and '/tests/' not in line:
                        test_only = False
                        break

        return not test_only


def main():
    parser = argparse.ArgumentParser(description="Run Opus-Conductor v2 on SWE-bench")
    parser.add_argument("--num", type=int, default=25, help="Number of tasks")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--random", action="store_true", help="Random selection")
    parser.add_argument("--output", "-o", type=str, default="conductor_v2_swebench.jsonl")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("=" * 70)
    print("OPUS-CONDUCTOR V2 - SWE-bench Verified")
    print("Docker-based iterative editing with multi-stage validation")
    print("=" * 70)
    print()

    # Load tasks
    tasks = load_swebench_verified()

    if args.random:
        random.seed(42)
        tasks = random.sample(tasks, min(args.num, len(tasks)))
    else:
        tasks = tasks[args.start:args.start + args.num]

    print(f"Running {len(tasks)} tasks...")
    print("-" * 70)

    results = []

    for i, task in enumerate(tasks):
        print(f"\n[{i+1}/{len(tasks)}] Task: {task.instance_id}")
        print(f"  {task.problem_statement[:60]}...")

        # Get Docker image
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
            conductor = ConductorSWEBench(
                docker_executor=docker_executor,
                max_steps=30,
            )

            result = conductor.run(task)
            results.append(result)

            status = "PASS" if result.success else "FAIL"
            print(f"  Result: {status}, steps={result.steps}, cost=${result.cost:.4f}, time={result.time:.1f}s")

            # Save incremental results
            with open(args.output, 'a') as f:
                f.write(json.dumps(asdict(result)) + '\n')

        finally:
            docker_executor.cleanup()

    # Summary
    passed = sum(1 for r in results if r.success)

    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print()
    print(f"Tasks Solved: {passed}/{len(results)}")
    print(f"Solve Rate: {100*passed/len(results):.1f}%" if results else "N/A")
    print(f"Total Cost: ${sum(r.cost for r in results):.2f}")
    print(f"Total Time: {sum(r.time for r in results)/60:.1f} min")
    print(f"Avg Steps: {sum(r.steps for r in results)/len(results):.1f}" if results else "N/A")
    print()

    # Save summary
    summary_file = args.output.replace('.jsonl', '_summary.json')
    summary = {
        "timestamp": datetime.now().isoformat(),
        "num_tasks": len(tasks),
        "solved": passed,
        "solve_rate": passed / len(results) if results else 0,
        "total_cost": sum(r.cost for r in results),
        "total_time": sum(r.time for r in results),
    }
    Path(summary_file).write_text(json.dumps(summary, indent=2))
    print(f"Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
