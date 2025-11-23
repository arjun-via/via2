"""Runner for ALO-Optimized variant (optimized model choices for cost/quality)."""
import time
from typing import Optional

from alo.agentic_loops.core.costs import CostTracker
from benchmark.runners.base import BaseRunner, RunResult
from main import build_prompt_orchestrator, load_config


class ALOOptimizedRunner(BaseRunner):
    """Runs ALO pipeline with optimized model choices.

    Optimizations:
    - Context: Gemini 2.5 Flash (KEEP - massive context window)
    - Engineering: Qwen3-Coder 480B (UPGRADE - specialized, 20x cheaper than GLM-4.6)
    - Review: Kimi-K2-Thinking (UPGRADE - deep reasoning for catching bugs)

    Expected: Better quality at ~40% lower cost than original ALO.
    """

    def __init__(self, config_path: str = "config/config_alo_optimized.yaml"):
        self.config = load_config(config_path)
        self.orchestrator = None  # Lazy init

    @property
    def name(self) -> str:
        return "alo_optimized"

    def run(self, prompt: str, context: Optional[str] = None) -> RunResult:
        """
        Run ALO-Optimized on the prompt.

        Uses optimized model selection:
        - Keeps Gemini's massive context window for context phase
        - Upgrades to specialized Qwen3-Coder for engineering (20x cheaper!)
        - Upgrades to Kimi-K2-Thinking for deeper review
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
            "system": "alo_optimized",
            "cost_breakdown": cost_summary.get("by_model", {}),
            "history_length": len(state.history),
            "context_generated": state.context_summary,
            "optimizations": {
                "context": "gemini-2.5-flash (kept)",
                "engineering": "qwen3-coder-480b (upgraded from glm-4.6, 20x cheaper)",
                "review": "kimi-k2-thinking (upgraded for deep reasoning)"
            }
        }

        return RunResult(
            output=state.final_answer,
            elapsed_time=elapsed,
            cost=cost_summary.get("total_cost", 0.0),
            metadata=metadata,
            context_used=state.context_summary
        )
