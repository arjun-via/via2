"""Runners for Claude Sonnet 4.5 (with and without context)."""
import os
import time
from typing import Optional

from benchmark.runners.base import BaseRunner, RunResult

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


class SonnetContextRunner(BaseRunner):
    """Runs Sonnet 4.5 with context injected into prompt."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250929"):
        if Anthropic is None:
            raise ImportError("anthropic package required for Sonnet runner")

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")

        self.client = Anthropic(api_key=api_key)
        self.model = model
        # Pricing from config
        self.prompt_cost_per_1k = 0.003
        self.completion_cost_per_1k = 0.015

    @property
    def name(self) -> str:
        return "sonnet_context"

    def run(self, prompt: str, context: Optional[str] = None) -> RunResult:
        """Run Sonnet with context included in prompt."""
        # Build prompt with context
        if context:
            full_prompt = f"""You are an expert software engineer.

Repository Context:
{context}

Task:
{prompt}

Provide a complete, production-ready solution."""
        else:
            full_prompt = f"""You are an expert software engineer.

Task:
{prompt}

Provide a complete, production-ready solution."""

        start = time.perf_counter()

        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            temperature=0,
            messages=[{"role": "user", "content": full_prompt}]
        )

        elapsed = time.perf_counter() - start

        # Extract text
        output = ""
        for block in response.content:
            if hasattr(block, "text"):
                output += block.text

        # Calculate cost
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        cost = (prompt_tokens / 1000 * self.prompt_cost_per_1k +
                completion_tokens / 1000 * self.completion_cost_per_1k)

        metadata = {
            "system": "sonnet_context",
            "model": self.model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "context_provided": context is not None
        }

        return RunResult(
            output=output,
            elapsed_time=elapsed,
            cost=cost,
            metadata=metadata,
            context_used=context
        )


class SonnetRawRunner(BaseRunner):
    """Runs Sonnet 4.5 without context (baseline)."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250929"):
        if Anthropic is None:
            raise ImportError("anthropic package required for Sonnet runner")

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")

        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.prompt_cost_per_1k = 0.003
        self.completion_cost_per_1k = 0.015

    @property
    def name(self) -> str:
        return "sonnet_raw"

    def run(self, prompt: str, context: Optional[str] = None) -> RunResult:
        """Run Sonnet without context (ignores context parameter)."""
        full_prompt = f"""You are an expert software engineer.

Task:
{prompt}

Provide a complete, production-ready solution."""

        start = time.perf_counter()

        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            temperature=0,
            messages=[{"role": "user", "content": full_prompt}]
        )

        elapsed = time.perf_counter() - start

        # Extract text
        output = ""
        for block in response.content:
            if hasattr(block, "text"):
                output += block.text

        # Calculate cost
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        cost = (prompt_tokens / 1000 * self.prompt_cost_per_1k +
                completion_tokens / 1000 * self.completion_cost_per_1k)

        metadata = {
            "system": "sonnet_raw",
            "model": self.model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "context_provided": False
        }

        return RunResult(
            output=output,
            elapsed_time=elapsed,
            cost=cost,
            metadata=metadata,
            context_used=None
        )
