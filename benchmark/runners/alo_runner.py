"""Runner for ALO multi-agent system."""
import time
from typing import Optional

from alo.agentic_loops.core.costs import CostTracker
from benchmark.runners.base import BaseRunner, RunResult
from main import build_prompt_orchestrator, load_config


class ALORunner(BaseRunner):
    """Runs the full ALO pipeline (context → prompt → review)."""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = load_config(config_path)
        self.orchestrator = None  # Lazy init

    @property
    def name(self) -> str:
        return "alo"

    def run(self, prompt: str, context: Optional[str] = None) -> RunResult:
        """
        Run ALO on the prompt.

        Note: ALO generates its own context via the context agent,
        so the context parameter is ignored but captured for comparison.
        """
        # Build orchestrator fresh each time to reset state
        self.orchestrator = build_prompt_orchestrator(self.config)

        # Reset cost tracker
        cost_tracker = CostTracker.get_instance()
        cost_tracker.reset()

        # Run the pipeline
        start = time.perf_counter()
        state, elapsed, cost_summary = self.orchestrator.run(prompt)

        metadata = {
            "system": "alo",
            "cost_breakdown": cost_summary.get("by_model", {}),
            "history_length": len(state.history),
            "context_generated": state.context_summary
        }

        return RunResult(
            output=state.final_answer,
            elapsed_time=elapsed,
            cost=cost_summary.get("total_cost", 0.0),
            metadata=metadata,
            context_used=state.context_summary
        )
