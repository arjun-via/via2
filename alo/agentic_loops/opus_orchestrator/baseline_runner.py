"""
=============================================================================
SCRIPT NAME: baseline_runner.py
=============================================================================

Opus Baseline Runner - Single-call benchmark baseline.

INPUT FILES:
- Task description from user

OUTPUT FILES:
- BaselineResult with solution and metrics

VERSION: 1.0
LAST UPDATED: 2025-11-26

DESCRIPTION:
Single-call baseline where Opus 4.5 handles everything in one pass.
Used for benchmark comparison against orchestrated variants.

This answers the question: "Is orchestration overhead worth it?"

DEPENDENCIES:
- time (standard library)

=============================================================================
"""

from typing import Optional
from dataclasses import dataclass
import time

from .model_registry import get_model
from .multi_provider_client import MultiProviderClient, CompletionResult


@dataclass
class BaselineResult:
    """Result from baseline single-call execution."""
    content: str
    input_tokens: int
    output_tokens: int
    elapsed_time: float
    tokens_per_second: float
    cost: float
    model: str


BASELINE_SYSTEM_PROMPT = '''You are Claude Opus 4.5, solving a software engineering task in a single pass.

APPROACH:
1. First, analyze the problem thoroughly
2. Identify all relevant context and dependencies
3. Plan your solution carefully before coding
4. Implement a complete, working solution
5. Self-review for correctness, edge cases, and security

CONSTRAINTS:
- Produce immediately executable code
- Include all necessary imports
- Handle edge cases (empty input, None, type errors)
- No TODO comments - implement everything
- No external dependencies unless explicitly allowed
- Single file implementation unless multi-file is required

OUTPUT FORMAT:
Return the complete solution with:
1. Brief analysis of the problem (2-3 sentences)
2. Your implementation approach (bullet points)
3. The complete code (properly formatted)
4. Key test cases to verify correctness

CRITICAL: The code must be immediately runnable. No placeholders.
'''


class OpusBaselineRunner:
    """
    Single-call baseline runner.

    Opus handles everything in one pass:
    - Context analysis
    - Solution planning
    - Code generation
    - Self-review

    This is the benchmark baseline to compare orchestrated variants against.
    """

    def __init__(
        self,
        client: MultiProviderClient,
        model_name: str = "opus-4.5",
        logger=None
    ):
        """
        Initialize the baseline runner.

        Args:
            client: Multi-provider client for API calls
            model_name: Model to use (default: opus-4.5)
            logger: Optional logger instance
        """
        self.client = client
        self.model_config = get_model(model_name)
        self.logger = logger

    def run(
        self,
        task: str,
        context: Optional[str] = None,
        max_tokens: int = 16384,
        temperature: float = 0.2
    ) -> BaselineResult:
        """
        Execute task in a single call.

        Args:
            task: Task description
            context: Optional additional context
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            BaselineResult with solution and metrics
        """
        self._log(f"Baseline run starting: {task[:50]}...")

        # Build messages
        user_content = f"Task: {task}"
        if context:
            user_content += f"\n\nAdditional Context:\n{context}"

        messages = [
            {"role": "system", "content": BASELINE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        # Single API call
        start_time = time.time()
        result = self.client.complete(
            model_config=self.model_config,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        elapsed = time.time() - start_time

        self._log(f"Baseline complete: {result.output_tokens} tokens in {elapsed:.1f}s")

        return BaselineResult(
            content=result.content,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            elapsed_time=elapsed,
            tokens_per_second=result.tokens_per_second,
            cost=result.cost,
            model=self.model_config.id
        )

    def run_with_retry(
        self,
        task: str,
        context: Optional[str] = None,
        max_retries: int = 2,
        **kwargs
    ) -> BaselineResult:
        """
        Execute task with automatic retry on failure.

        Args:
            task: Task description
            context: Optional additional context
            max_retries: Maximum retry attempts
            **kwargs: Additional arguments passed to run()

        Returns:
            BaselineResult with solution and metrics
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return self.run(task, context, **kwargs)
            except Exception as e:
                last_error = e
                self._log(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)  # Exponential backoff

        raise Exception(f"All {max_retries + 1} attempts failed. Last error: {last_error}")

    def _log(self, message: str):
        """Log message if logger available."""
        if self.logger:
            self.logger.info(message)


def run_baseline_comparison(
    client: MultiProviderClient,
    task: str,
    context: Optional[str] = None
) -> dict:
    """
    Run baseline comparison for benchmarking.

    Returns dict with baseline metrics for comparison against orchestrated variants.

    Args:
        client: Multi-provider client
        task: Task description
        context: Optional context

    Returns:
        Dict with baseline metrics
    """
    runner = OpusBaselineRunner(client)
    result = runner.run(task, context)

    return {
        "variant": "opus-baseline",
        "model": result.model,
        "tokens_generated": result.output_tokens,
        "elapsed_time": result.elapsed_time,
        "tokens_per_second": result.tokens_per_second,
        "cost": result.cost,
        "content_preview": result.content[:200] if result.content else ""
    }
