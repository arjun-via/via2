"""Runner for ALO-BestInClass using premium models."""
import time
from typing import Optional

from benchmark.runners.base import BaseRunner, RunResult
from main import build_prompt_orchestrator, load_config
from alo.agentic_loops.core.costs import CostTracker


class ALOBestInClassRunner(BaseRunner):
    """Runs ALO pipeline with best-in-class premium models.

    Uses:
    - Gemini 3 Pro for context analysis (2M context window)
    - Claude Sonnet 4.5 for engineering (best coding model)
    - GPT-5.1 for review (deep reasoning)
    """

    def __init__(self, config_path: str = "config/config_alo_bestinclass.yaml"):
        self.config = load_config(config_path)
        self.orchestrator = None

    @property
    def name(self) -> str:
        return "alo_bestinclass"

    def run(self, prompt: str, context: Optional[str] = None) -> RunResult:
        """Run ALO-BestInClass on a prompt."""
        self.orchestrator = build_prompt_orchestrator(self.config)

        cost_tracker = CostTracker.get_instance()
        cost_tracker.reset()

        start = time.perf_counter()
        state, elapsed, cost_summary = self.orchestrator.run(prompt)
        actual_elapsed = time.perf_counter() - start

        output = state.final_answer or state.engineering_output or ""

        return RunResult(
            output=output,
            elapsed_time=actual_elapsed,
            cost=cost_summary.get("total_cost", 0.0),
            metadata={
                "system": "alo_bestinclass",
                "config": "Gemini3Pro + Sonnet4.5 + GPT5.1",
                "cost_breakdown": cost_summary,
                "state_history": len(state.history)
            },
            context_used=context
        )
