"""
=============================================================================
ALO v2.0 Worker Dispatch System
=============================================================================

Intelligent worker selection based on task characteristics.

WORKERS:
- Kimi K2: Default worker - fast (700ms), cheap ($0.20/M), 100% accuracy
- Gemini 3 Flash: Large context worker - 1M tokens, 78% SWE-bench

SELECTION CRITERIA:
- Context size: Use Gemini 3 Flash when context > 100K tokens
- Task complexity: (future) Route complex tasks differently
- Cost optimization: Prefer Kimi K2 for cost efficiency
=============================================================================
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum

from .config import Config
from .clients import ClientFactory, BaseClient, ModelResponse


class WorkerType(Enum):
    """Available worker types"""
    KIMI_K2 = "kimi-k2"
    GEMINI_3_FLASH = "gemini-3-flash"


@dataclass
class WorkerSelection:
    """Result of worker selection"""
    worker_type: WorkerType
    reason: str
    estimated_cost_per_1k: float


class WorkerDispatcher:
    """
    Intelligent worker selection and dispatch.

    Selects the optimal worker based on:
    - Context size (token count)
    - Task type
    - Cost constraints
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

        # Initialize workers
        self._workers = {
            WorkerType.KIMI_K2: ClientFactory.create(
                self.config.get_model("kimi-k2"),
                self.config.openrouter_api_key
            ),
            WorkerType.GEMINI_3_FLASH: ClientFactory.create(
                self.config.get_model("gemini-3-flash"),
                self.config.openrouter_api_key
            )
        }

        # Context threshold for switching to Gemini
        self.large_context_threshold = self.config.large_context_threshold

    def select_worker(
        self,
        context_size: int = 0,
        task_type: str = "general",
        prefer_speed: bool = True
    ) -> WorkerSelection:
        """
        Select the optimal worker for a task.

        Args:
            context_size: Estimated token count for the task
            task_type: Type of task (general, localization, fix, etc.)
            prefer_speed: Whether to prefer faster workers

        Returns:
            WorkerSelection with worker type and reasoning
        """
        # Large context -> Gemini 3 Flash (1M token limit)
        if context_size > self.large_context_threshold:
            return WorkerSelection(
                worker_type=WorkerType.GEMINI_3_FLASH,
                reason=f"Context size ({context_size:,} tokens) exceeds threshold ({self.large_context_threshold:,})",
                estimated_cost_per_1k=0.375  # Average of prompt/completion
            )

        # Default -> Kimi K2 (fast, cheap, accurate)
        return WorkerSelection(
            worker_type=WorkerType.KIMI_K2,
            reason="Default worker: fast, cheap, 100% accuracy on evaluation",
            estimated_cost_per_1k=0.4  # Average of prompt/completion
        )

    def get_worker(self, worker_type: WorkerType) -> BaseClient:
        """Get a worker client by type"""
        return self._workers[worker_type]

    def dispatch(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context_size: Optional[int] = None,
        task_type: str = "general",
        max_tokens: int = 4096
    ) -> tuple[ModelResponse, WorkerSelection]:
        """
        Select and call the appropriate worker.

        Args:
            prompt: The prompt to send
            system_prompt: Optional system prompt
            context_size: Token count (estimated from prompt if not provided)
            task_type: Type of task for routing
            max_tokens: Max response tokens

        Returns:
            Tuple of (ModelResponse, WorkerSelection)
        """
        # Estimate context size if not provided
        if context_size is None:
            # Rough estimate: 4 chars per token
            context_size = len(prompt) // 4

        # Select worker
        selection = self.select_worker(context_size, task_type)

        # Get and call worker
        worker = self.get_worker(selection.worker_type)
        messages = [{"role": "user", "content": prompt}]

        response = worker.generate(
            messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens
        )

        return response, selection

    def dispatch_with_fallback(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096
    ) -> tuple[ModelResponse, WorkerSelection]:
        """
        Dispatch with automatic fallback on failure.

        Tries Kimi K2 first, falls back to Gemini 3 Flash on error.
        """
        # Try primary worker (Kimi K2)
        try:
            selection = WorkerSelection(
                worker_type=WorkerType.KIMI_K2,
                reason="Primary worker",
                estimated_cost_per_1k=0.4
            )
            worker = self.get_worker(WorkerType.KIMI_K2)
            messages = [{"role": "user", "content": prompt}]
            response = worker.generate(messages, system_prompt=system_prompt, max_tokens=max_tokens)
            return response, selection

        except Exception as e:
            # Fallback to Gemini 3 Flash
            selection = WorkerSelection(
                worker_type=WorkerType.GEMINI_3_FLASH,
                reason=f"Fallback after Kimi K2 error: {str(e)[:100]}",
                estimated_cost_per_1k=0.375
            )
            worker = self.get_worker(WorkerType.GEMINI_3_FLASH)
            messages = [{"role": "user", "content": prompt}]
            response = worker.generate(messages, system_prompt=system_prompt, max_tokens=max_tokens)
            return response, selection


def test_dispatcher():
    """Test the worker dispatcher"""
    dispatcher = WorkerDispatcher()

    # Test selection logic
    print("Testing worker selection...")

    # Small context -> Kimi K2
    selection = dispatcher.select_worker(context_size=10000)
    print(f"  10K tokens: {selection.worker_type.value} - {selection.reason}")

    # Large context -> Gemini 3 Flash
    selection = dispatcher.select_worker(context_size=150000)
    print(f"  150K tokens: {selection.worker_type.value} - {selection.reason}")

    # Test actual dispatch
    print("\nTesting dispatch...")
    response, selection = dispatcher.dispatch(
        prompt="What is 2+2? Answer with just the number.",
        task_type="general"
    )
    print(f"  Worker: {selection.worker_type.value}")
    print(f"  Response: {response.content}")
    print(f"  Tokens: {response.total_tokens}, Cost: ${response.cost:.6f}")

    print("\nWorker dispatch test complete!")


if __name__ == "__main__":
    test_dispatcher()
