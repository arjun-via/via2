"""
=============================================================================
SCRIPT NAME: opus_baseline_runner.py
=============================================================================

Baseline runner for Opus 4.5 with NO orchestration.
This is the control group - just Opus with its full context window,
single API call, no agents, no loops, no orchestration overhead.

This establishes the TRUE baseline for what Opus can do alone,
which the Meta-Orchestrator must beat to justify its complexity.

USAGE:
    runner = OpusBaselineRunner()
    result = runner.run("Implement a rate limiter...")

VERSION: 1.0
LAST UPDATED: 2025-11-26
=============================================================================
"""
import os
import time
from dataclasses import dataclass
from typing import Optional

from anthropic import Anthropic


@dataclass
class RunResult:
    """Result from a benchmark run."""
    output: str
    elapsed_time: float
    cost: float
    input_tokens: int
    output_tokens: int
    model: str


class OpusBaselineRunner:
    """
    Baseline runner using Opus 4.5 with NO orchestration.

    This is the simplest possible approach:
    1. Send prompt to Opus
    2. Get response
    3. Done

    No context agent, no engineering loops, no review loops.
    Just pure Opus reasoning in a single call.
    """

    # Opus 4.5 pricing (per million tokens)
    PROMPT_COST_PER_M = 5.0    # $5 per million input tokens
    COMPLETION_COST_PER_M = 25.0  # $25 per million output tokens

    SYSTEM_PROMPT = """You are an expert software engineer. When given a coding task:

1. Analyze the requirements carefully
2. Design a clean, working solution
3. Implement it in Python
4. Include necessary imports
5. Add docstrings and comments
6. Handle edge cases

CRITICAL CONSTRAINTS:
- Use ONLY Python standard library (no external packages like redis, numpy, etc.)
- Implement as a SINGLE self-contained Python file
- Code must be executable as-is
- Include a simple test/demo at the bottom using if __name__ == "__main__"

Return your complete implementation in a Python code block."""

    def __init__(self):
        """Initialize Opus baseline runner."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")

        self.client = Anthropic(api_key=api_key)
        self.model = "claude-opus-4-5-20251101"

    def run(self, prompt: str, context: Optional[str] = None) -> RunResult:
        """
        Run Opus on a prompt with no orchestration.

        Args:
            prompt: The coding task to solve
            context: Optional additional context (e.g., existing code)

        Returns:
            RunResult with output, timing, and cost information
        """
        # Build the user message
        user_message = prompt
        if context:
            user_message = f"Context:\n{context}\n\nTask:\n{prompt}"

        # Time the API call
        start_time = time.time()

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=self.SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        elapsed_time = time.time() - start_time

        # Extract response
        output = response.content[0].text

        # Calculate cost
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        cost = (
            (input_tokens / 1_000_000) * self.PROMPT_COST_PER_M +
            (output_tokens / 1_000_000) * self.COMPLETION_COST_PER_M
        )

        return RunResult(
            output=output,
            elapsed_time=elapsed_time,
            cost=cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model
        )


class OpusBaselineWithThinkingRunner:
    """
    Opus baseline with extended thinking enabled.

    Uses Opus's built-in extended thinking capability for more
    complex reasoning before generating the solution.
    """

    PROMPT_COST_PER_M = 5.0
    COMPLETION_COST_PER_M = 25.0

    SYSTEM_PROMPT = """You are an expert software engineer. When given a coding task:

1. Think through the problem carefully
2. Consider edge cases and potential issues
3. Design a clean, efficient solution
4. Implement it in Python

CRITICAL CONSTRAINTS:
- Use ONLY Python standard library (no external packages)
- Implement as a SINGLE self-contained Python file
- Code must be executable as-is
- Include tests using if __name__ == "__main__"

Return your complete implementation in a Python code block."""

    def __init__(self, thinking_budget: int = 10000):
        """
        Initialize Opus with thinking runner.

        Args:
            thinking_budget: Max tokens for extended thinking (default 10k)
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")

        self.client = Anthropic(api_key=api_key)
        self.model = "claude-opus-4-5-20251101"
        self.thinking_budget = thinking_budget

    def run(self, prompt: str, context: Optional[str] = None) -> RunResult:
        """Run Opus with extended thinking enabled."""
        user_message = prompt
        if context:
            user_message = f"Context:\n{context}\n\nTask:\n{prompt}"

        start_time = time.time()

        response = self.client.messages.create(
            model=self.model,
            max_tokens=16384,
            thinking={
                "type": "enabled",
                "budget_tokens": self.thinking_budget
            },
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        elapsed_time = time.time() - start_time

        # Extract text content (skip thinking blocks)
        output_parts = []
        for block in response.content:
            if block.type == "text":
                output_parts.append(block.text)

        output = "\n".join(output_parts)

        # Calculate cost
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        cost = (
            (input_tokens / 1_000_000) * self.PROMPT_COST_PER_M +
            (output_tokens / 1_000_000) * self.COMPLETION_COST_PER_M
        )

        return RunResult(
            output=output,
            elapsed_time=elapsed_time,
            cost=cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=f"{self.model}+thinking"
        )


if __name__ == "__main__":
    # Quick test
    runner = OpusBaselineRunner()

    test_prompt = "Implement a simple thread-safe counter class in Python with increment, decrement, and get_value methods."

    print("Testing Opus Baseline Runner...")
    print(f"Prompt: {test_prompt[:50]}...")

    result = runner.run(test_prompt)

    print(f"\nResult:")
    print(f"  Time: {result.elapsed_time:.2f}s")
    print(f"  Cost: ${result.cost:.4f}")
    print(f"  Tokens: {result.input_tokens} in / {result.output_tokens} out")
    print(f"\nOutput preview:\n{result.output[:500]}...")
