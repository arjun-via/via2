"""
=============================================================================
SCRIPT NAME: agentic_loop.py
=============================================================================

Opus Orchestrator - Single-model iterative Docker loop with Claude Opus 4.5.

SYSTEM: Opus Orchestrator (one of three systems in Via2)
  - ALO: Multi-model pipeline (Gemini, GPT, GLM, Kimi)
  - Opus Orchestrator: Single-model Docker loop (Claude Opus 4.5) - THIS SYSTEM
  - Dynamic: Adaptive model selection with learning

INPUT FILES:
- SWE-bench instance (problem statement, repo info)
- Optional context priming (relevant files identified by Gemini)

OUTPUT FILES:
- Git patch with the fix
- Trajectory JSON with all steps

VERSION: 1.0
LAST UPDATED: 2025-11-28

DESCRIPTION:
Core component of the Opus Orchestrator system. Implements an iterative
THINK → ACT → OBSERVE loop where Claude Opus 4.5:
1. THINK: Analyzes the problem and decides on an action
2. ACT: Executes ONE bash command in a Docker container
3. OBSERVE: Receives real output from the container
4. Repeats until the fix is complete

Key techniques:
- One command per response (prevents hallucination)
- Docker-based execution in SWE-bench containers
- Patch validation ensures source file changes (not just test files)
- Hallucination detection catches imagined outputs

This is the KEY component that enables 75%+ resolution on SWE-bench.

MODEL: claude-opus-4-5-20251101 (Opus 4.5)

DEPENDENCIES:
- anthropic
- docker_executor (local)

=============================================================================
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

import anthropic

from .docker_executor import DockerExecutor


@dataclass
class Step:
    """A single step in the agentic loop."""
    step_num: int
    thought: str
    action: str
    observation: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgenticResult:
    """Result from the agentic loop."""
    success: bool
    patch: str
    steps: List[Step]
    total_cost: float
    total_tokens: int
    error: Optional[str] = None


# The system prompt that makes Opus effective at SWE-bench
SYSTEM_PROMPT = r'''You are an expert software engineer fixing a bug in a Python repository.

CRITICAL RULES:
1. ONLY write ONE bash command per response
2. WAIT for the actual output - DO NOT imagine/hallucinate command output
3. You MUST edit actual source files (not test files) to fix the bug
4. DO NOT submit until you have modified source code files

MANDATORY WORKFLOW:
Step 1: Find the source file containing the bug
```bash
find . -name "*.py" -path "*/packagename/*" | head -20
```

Step 2: Read the buggy source file to understand it
```bash
cat ./path/to/source.py
```

Step 3: EDIT the source file using sed or python
```bash
sed -i 's/buggy_code/fixed_code/g' ./path/to/source.py
```

Step 4: Verify your edit worked
```bash
cat ./path/to/source.py | grep -A5 "fixed_code"
```

Step 5: Check git diff shows SOURCE file changes
```bash
git add -A && git diff --cached
```

Step 6: If diff shows source file changes, say SUBMIT

EDITING METHODS:
- Small changes: sed -i 's/old/new/g' file.py
- Multi-line: Use python with content.replace()
- Full rewrite: cat > file.py << 'EOF' ... EOF

FORBIDDEN:
- DO NOT write test_*.py files as your fix
- DO NOT hallucinate command output
- DO NOT submit without editing source files
- DO NOT write "Output:" followed by imagined results

The diff in step 5 MUST show changes to files like:
- astropy/modeling/separable.py (source)
- django/db/models/query.py (source)
NOT files like:
- test_fix.py (test script you created)
- reproduce.py (reproduction script)

Say SUBMIT only after git diff shows source file changes.
'''


def detect_hallucinated_output(response: str) -> bool:
    """
    Detect if the model is hallucinating command output instead of waiting for real output.

    Signs of hallucination:
    - Multiple ```bash blocks with "Output:" between them
    - Writing "Output:" or "Result:" followed by text after a command block
    """
    # Check for "Output:" or similar after a bash block
    patterns = [
        r'```bash\n.*?```\s*\n\s*(Output|Result|stdout|stderr|This outputs?|The output|returns?)\s*[:=]',
        r'```\n.*?```\s*\n\s*(Output|Result|stdout|stderr|This outputs?|The output|returns?)\s*[:=]',
        r'```bash\n.*?```\s*\n\s*```\s*\n',  # Multiple code blocks in sequence
    ]

    for pattern in patterns:
        if re.search(pattern, response, re.DOTALL | re.IGNORECASE):
            return True

    # Count bash blocks - if more than 1, likely hallucinating
    bash_blocks = re.findall(r'```bash\n.*?```', response, re.DOTALL)
    if len(bash_blocks) > 1:
        return True

    return False


def parse_bash_command(response: str) -> Optional[str]:
    """Extract bash command from LLM response."""
    # Look for ```bash blocks
    match = re.search(r'```bash\n(.*?)```', response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Also try generic ``` blocks
    match = re.search(r'```\n(.*?)```', response, re.DOTALL)
    if match:
        cmd = match.group(1).strip()
        # Check it looks like a command (not code)
        if cmd.startswith(('find ', 'grep ', 'cat ', 'ls ', 'cd ', 'python', 'pytest',
                          'sed ', 'echo ', 'git ', 'head ', 'tail ', 'mkdir ', 'touch ')):
            return cmd

    return None


def truncate_output(output: str, max_chars: int = 15000) -> str:
    """Truncate long outputs to avoid context overflow."""
    if len(output) <= max_chars:
        return output

    half = max_chars // 2
    return output[:half] + f"\n\n[... truncated {len(output) - max_chars} chars ...]\n\n" + output[-half:]


class AgenticLoop:
    """
    Opus Orchestrator's core agentic loop for solving SWE-bench instances.

    This is the main component of the Opus Orchestrator system, one of three
    agent systems in the Via2 repository:
    - ALO: Multi-model pipeline (Gemini, GPT, GLM, Kimi)
    - Opus Orchestrator: Single-model Docker loop (Claude Opus 4.5) - THIS SYSTEM
    - Dynamic: Adaptive model selection with learning

    Uses Claude Opus 4.5 in an iterative THINK → ACT → OBSERVE loop to
    explore, understand, and fix bugs by executing bash commands in Docker.

    Key Features:
    - One command per LLM response (prevents hallucination)
    - Docker-based execution in SWE-bench containers
    - Patch validation ensures source file changes
    - Hallucination detection catches imagined outputs
    """

    def __init__(
        self,
        model: str = "claude-opus-4-5-20251101",
        max_steps: int = 30,
        cost_limit: float = 10.0,  # $10 per instance
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the agentic loop.

        Args:
            model: Claude model to use
            max_steps: Maximum number of steps before giving up
            cost_limit: Maximum cost in dollars per instance
            logger: Optional logger
        """
        self.model = model
        self.max_steps = max_steps
        self.cost_limit = cost_limit
        self.logger = logger or logging.getLogger("opus.agentic")

        # Initialize Anthropic client
        self.client = anthropic.Anthropic()

        # Pricing per 1M tokens (Opus pricing)
        self.input_cost_per_m = 15.0   # $15 per 1M input tokens
        self.output_cost_per_m = 75.0  # $75 per 1M output tokens

    def _validate_patch_has_source_changes(self, patch: str) -> bool:
        """
        Check if the patch contains changes to actual source files,
        not just test files or newly created scripts.

        Returns:
            True if patch contains changes to source code files
        """
        # Parse the diff to find changed files
        file_pattern = re.compile(r'diff --git a/([^ ]+) b/([^ ]+)')
        new_file_pattern = re.compile(r'new file mode')

        # Patterns for test/non-source files
        test_patterns = [
            r'^test_',           # test_*.py files created by the agent
            r'/tests?/',         # files in tests/ or test/ directories
            r'_test\.py$',       # *_test.py files
            r'test_.*\.py$',     # test_*.py anywhere in path
            r'^conftest\.py$',   # pytest config
            r'\.md$',            # markdown docs
            r'^setup\.py$',      # setup files
            r'requirements',     # requirements files
        ]

        source_files_changed = []
        test_files_changed = []

        lines = patch.split('\n')
        current_file = None
        is_new_file = False

        for i, line in enumerate(lines):
            match = file_pattern.match(line)
            if match:
                current_file = match.group(2)  # Use the 'b/' path
                is_new_file = False
                continue

            if 'new file mode' in line:
                is_new_file = True
                continue

            if current_file and (line.startswith('+++') or line.startswith('---')):
                # Check if it's a test file
                is_test = False
                for pattern in test_patterns:
                    if re.search(pattern, current_file, re.IGNORECASE):
                        is_test = True
                        break

                # New files created by agent are likely test scripts
                if is_new_file and current_file.endswith('.py'):
                    # Check if it looks like a test/demo script the agent created
                    if 'test' in current_file.lower() or 'demo' in current_file.lower():
                        is_test = True
                    # Root-level new .py files are probably test scripts
                    elif '/' not in current_file:
                        is_test = True

                if is_test:
                    if current_file not in test_files_changed:
                        test_files_changed.append(current_file)
                else:
                    if current_file not in source_files_changed:
                        source_files_changed.append(current_file)

                current_file = None

        self.logger.debug(f"Source files changed: {source_files_changed}")
        self.logger.debug(f"Test files changed: {test_files_changed}")

        return len(source_files_changed) > 0

    def run(
        self,
        problem_statement: str,
        docker_image: str,
        context_files: Optional[Dict[str, str]] = None,
        test_cmd: Optional[str] = None
    ) -> AgenticResult:
        """
        Run the agentic loop to solve a problem.

        Args:
            problem_statement: The issue description
            docker_image: Docker image for the SWE-bench instance
            context_files: Optional pre-identified relevant files and their contents
            test_cmd: Optional test command to verify the fix

        Returns:
            AgenticResult with patch and trajectory
        """
        steps: List[Step] = []
        total_input_tokens = 0
        total_output_tokens = 0

        # Build initial user message
        initial_message = f"## Problem Statement\n\n{problem_statement}\n\n"

        if context_files:
            initial_message += "## Relevant Files (pre-identified)\n\n"
            for path, content in context_files.items():
                initial_message += f"### {path}\n```python\n{content[:5000]}\n```\n\n"

        initial_message += "Please analyze this issue and fix the bug. Start by exploring the codebase to understand the problem."

        # Message history for the conversation
        messages = [{"role": "user", "content": initial_message}]

        self.logger.info(f"Starting agentic loop with image: {docker_image}")

        with DockerExecutor(image=docker_image) as executor:
            for step_num in range(1, self.max_steps + 1):
                # Check cost limit
                current_cost = (
                    (total_input_tokens / 1_000_000) * self.input_cost_per_m +
                    (total_output_tokens / 1_000_000) * self.output_cost_per_m
                )
                if current_cost > self.cost_limit:
                    self.logger.warning(f"Cost limit reached: ${current_cost:.2f}")
                    return AgenticResult(
                        success=False,
                        patch="",
                        steps=steps,
                        total_cost=current_cost,
                        total_tokens=total_input_tokens + total_output_tokens,
                        error=f"Cost limit exceeded: ${current_cost:.2f}"
                    )

                # Get LLM response
                self.logger.debug(f"Step {step_num}: Calling {self.model}")

                try:
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=4096,
                        system=SYSTEM_PROMPT,
                        messages=messages
                    )
                except Exception as e:
                    self.logger.error(f"API error: {e}")
                    return AgenticResult(
                        success=False,
                        patch="",
                        steps=steps,
                        total_cost=current_cost,
                        total_tokens=total_input_tokens + total_output_tokens,
                        error=f"API error: {e}"
                    )

                # Track tokens
                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens

                # Extract response text
                thought = response.content[0].text

                # Check for submission
                if "SUBMIT" in thought.upper():
                    # Get the final diff
                    diff_result = executor.get_diff()
                    patch = diff_result.output

                    if patch.strip():
                        # Validate that patch contains SOURCE file changes, not just test files
                        has_source_changes = self._validate_patch_has_source_changes(patch)

                        if has_source_changes:
                            self.logger.info(f"Submission received after {step_num} steps")
                            steps.append(Step(
                                step_num=step_num,
                                thought=thought,
                                action="SUBMIT",
                                observation=f"Patch submitted:\n{patch[:500]}..."
                            ))

                            final_cost = (
                                (total_input_tokens / 1_000_000) * self.input_cost_per_m +
                                (total_output_tokens / 1_000_000) * self.output_cost_per_m
                            )

                            return AgenticResult(
                                success=True,
                                patch=patch,
                                steps=steps,
                                total_cost=final_cost,
                                total_tokens=total_input_tokens + total_output_tokens
                            )
                        else:
                            # Only test files modified, reject
                            observation = """REJECTED: Your patch only contains test files or scripts, not actual source code fixes.
You MUST modify the actual source code to fix the bug, not just write test scripts.
Please identify and edit the buggy source file(s) in the repository (not test_*.py or scripts you created).
Continue exploring the codebase and implement the actual fix."""
                            messages.append({"role": "assistant", "content": thought})
                            messages.append({"role": "user", "content": observation})
                            steps.append(Step(
                                step_num=step_num,
                                thought=thought,
                                action="SUBMIT (rejected: no source changes)",
                                observation=observation
                            ))
                            continue
                    else:
                        # No changes made, continue
                        observation = "No changes detected. Please make the necessary edits first."
                        messages.append({"role": "assistant", "content": thought})
                        messages.append({"role": "user", "content": observation})
                        steps.append(Step(
                            step_num=step_num,
                            thought=thought,
                            action="SUBMIT (no changes)",
                            observation=observation
                        ))
                        continue

                # Check for hallucinated output first
                if detect_hallucinated_output(thought):
                    self.logger.warning("Detected hallucinated output in response")
                    observation = """WARNING: You are imagining command output instead of waiting for real results.
IMPORTANT: Write ONLY ONE bash command, then STOP and wait for me to show you the actual output.
Do NOT write "Output:" or imagine what the command returns.
Do NOT write multiple bash blocks in one response.
Please try again with just ONE command."""
                    action = "(hallucinated output)"
                    steps.append(Step(
                        step_num=step_num,
                        thought=thought[:500] + "...(truncated)",
                        action=action,
                        observation=observation
                    ))
                    messages.append({"role": "assistant", "content": thought})
                    messages.append({"role": "user", "content": f"OBSERVATION:\n{observation}"})
                    continue

                # Parse bash command
                action = parse_bash_command(thought)

                if action:
                    # Execute the command
                    self.logger.debug(f"Executing: {action[:80]}...")
                    result = executor.execute(action, timeout=120)
                    observation = truncate_output(result.output)

                    if result.return_code != 0:
                        observation = f"[Exit code: {result.return_code}]\n{observation}"
                else:
                    # No command found, ask for action
                    observation = "No bash command found in your response. Please provide a command in a ```bash block."
                    action = "(no command)"

                # Record step
                steps.append(Step(
                    step_num=step_num,
                    thought=thought,
                    action=action,
                    observation=observation
                ))

                # Add to conversation
                messages.append({"role": "assistant", "content": thought})
                messages.append({"role": "user", "content": f"OBSERVATION:\n{observation}"})

                self.logger.info(f"Step {step_num}: {action[:50]}... -> {len(observation)} chars")

        # Exhausted max steps
        final_cost = (
            (total_input_tokens / 1_000_000) * self.input_cost_per_m +
            (total_output_tokens / 1_000_000) * self.output_cost_per_m
        )

        return AgenticResult(
            success=False,
            patch="",
            steps=steps,
            total_cost=final_cost,
            total_tokens=total_input_tokens + total_output_tokens,
            error=f"Exceeded max steps ({self.max_steps})"
        )

    def save_trajectory(self, result: AgenticResult, output_path: str):
        """Save the trajectory to a JSON file."""
        trajectory = {
            "success": result.success,
            "patch": result.patch,
            "total_cost": result.total_cost,
            "total_tokens": result.total_tokens,
            "error": result.error,
            "steps": [
                {
                    "step_num": s.step_num,
                    "thought": s.thought,
                    "action": s.action,
                    "observation": s.observation,
                    "timestamp": s.timestamp
                }
                for s in result.steps
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(trajectory, f, indent=2)


# Quick test
def test_agentic_loop():
    """Test the agentic loop with a simple problem."""
    logging.basicConfig(level=logging.INFO)

    loop = AgenticLoop(max_steps=5)

    # Simple test problem
    result = loop.run(
        problem_statement="Create a file called hello.py that prints 'Hello World'",
        docker_image="python:3.11-slim"
    )

    print(f"Success: {result.success}")
    print(f"Steps: {len(result.steps)}")
    print(f"Cost: ${result.total_cost:.4f}")
    print(f"Patch:\n{result.patch[:500] if result.patch else 'None'}")


if __name__ == "__main__":
    test_agentic_loop()
