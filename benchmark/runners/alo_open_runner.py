"""Runner for ALO-Open variant (ALO orchestration with only open-source models)."""
import time
from typing import Optional

from alo.agentic_loops.core.costs import CostTracker
from benchmark.runners.base import BaseRunner, RunResult
from main import build_prompt_orchestrator, load_config


class ALOOpenRunner(BaseRunner):
    """Runs ALO pipeline with only open-source models.

    Uses:
    - Context: Kimi-K2-Thinking (reasoning for deep analysis)
    - Engineering: Qwen3-Coder (specialized for code generation)
    - Review: Kimi-K2 (proven for review/critique)

    All accessed via OpenRouter/Cerebras APIs.
    """

    def __init__(self, config_path: str = "config/config_alo_open.yaml"):
        self.config = load_config(config_path)
        self.orchestrator = None  # Lazy init

    @property
    def name(self) -> str:
        return "alo_open"

    def run(self, prompt: str, context: Optional[str] = None) -> RunResult:
        """
        Run ALO-Open on the prompt.

        ALO-Open uses the same orchestration as ALO but with only open-source
        models instead of proprietary ones (Gemini, GPT, Sonnet).

        This tests whether open-source models can match proprietary performance
        with the same multi-agent architecture.
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
            "system": "alo_open",
            "cost_breakdown": cost_summary.get("by_model", {}),
            "history_length": len(state.history),
            "context_generated": state.context_summary,
            "all_agents_open_source": True,
            "models_used": {
                "context": "kimi-k2-thinking",
                "engineering": "qwen-3-coder-turbo",
                "review": "kimi-k2"
            }
        }

        return RunResult(
            output=state.final_answer,
            elapsed_time=elapsed,
            cost=cost_summary.get("total_cost", 0.0),
            metadata=metadata,
            context_used=state.context_summary
        )
