"""Runner for ALO-Opus variant (ALO orchestration with Opus 4.5 for all phases)."""
import time
from typing import Optional

from alo.agentic_loops.core.costs import CostTracker
from benchmark.runners.base import BaseRunner, RunResult
from main import build_prompt_orchestrator, load_config


class ALOOpusRunner(BaseRunner):
    """Runs ALO pipeline with Opus 4.5 for all agents (context, prompt, review)."""

    def __init__(self, config_path: str = "config/config_alo_opus.yaml"):
        self.config = load_config(config_path)
        self.orchestrator = None  # Lazy init

    @property
    def name(self) -> str:
        return "alo_opus"

    def run(self, prompt: str, context: Optional[str] = None) -> RunResult:
        """
        Run ALO-Opus on the prompt.

        ALO-Opus uses the same orchestration as ALO but with Opus 4.5
        for all phases. This tests whether the more capable (and expensive)
        Opus model produces better results through the ALO pipeline.
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
            "system": "alo_opus",
            "cost_breakdown": cost_summary.get("by_model", {}),
            "history_length": len(state.history),
            "context_generated": state.context_summary,
            "all_agents_use_opus": True
        }

        return RunResult(
            output=state.final_answer,
            elapsed_time=elapsed,
            cost=cost_summary.get("total_cost", 0.0),
            metadata=metadata,
            context_used=state.context_summary
        )
