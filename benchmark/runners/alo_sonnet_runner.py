"""Runner for ALO-Sonnet variant (ALO orchestration with Sonnet for all phases)."""
import time
from typing import Optional

from alo.agentic_loops.core.costs import CostTracker
from benchmark.runners.base import BaseRunner, RunResult
from main import build_prompt_orchestrator, load_config


class ALOSonnetRunner(BaseRunner):
    """Runs ALO pipeline but with Sonnet 4.5 for all agents (context, prompt, review)."""

    def __init__(self, config_path: str = "config/config_alo_sonnet.yaml"):
        self.config = load_config(config_path)
        self.orchestrator = None  # Lazy init

    @property
    def name(self) -> str:
        return "alo_sonnet"

    def run(self, prompt: str, context: Optional[str] = None) -> RunResult:
        """
        Run ALO-Sonnet on the prompt.

        ALO-Sonnet uses the same orchestration as ALO but with Sonnet 4.5
        for all phases instead of mixed models (Gemini/GLM/Kimi).

        This isolates whether ALO's value comes from orchestration or model choices.
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
            "system": "alo_sonnet",
            "cost_breakdown": cost_summary.get("by_model", {}),
            "history_length": len(state.history),
            "context_generated": state.context_summary,
            "all_agents_use_sonnet": True
        }

        return RunResult(
            output=state.final_answer,
            elapsed_time=elapsed,
            cost=cost_summary.get("total_cost", 0.0),
            metadata=metadata,
            context_used=state.context_summary
        )
