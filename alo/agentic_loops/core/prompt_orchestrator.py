import time
from typing import Any, Tuple

from alo.agentic_loops.core.state import LoopState


class PromptOrchestrator:
    """Orchestrate prompt → context → answer with review."""

    def __init__(
        self,
        context_agent: Any,
        prompt_agent: Any,
        logger: Any | None = None,
        trace_recorder: Any | None = None,
        cost_tracker: Any | None = None,
    ) -> None:
        self.context_agent = context_agent
        self.prompt_agent = prompt_agent
        self.logger = logger
        self.trace_recorder = trace_recorder
        self.cost_tracker = cost_tracker

    def run(self, prompt: str) -> Tuple[LoopState, float, dict]:
        if self.cost_tracker:
            self.cost_tracker.reset()

        state = LoopState(issue_description=prompt, repo_path="")
        if self.logger:
            self.logger.info("Starting prompt run")
        if self.trace_recorder:
            self.trace_recorder.record("start", "prompt_orchestrator", {"prompt": prompt})

        start = time.perf_counter()
        try:
            state = self.context_agent.run(state)
        except Exception as exc:
            state.add_history("context_error", error=str(exc))
            state.final_answer = f"Context step failed: {exc}"
            elapsed = time.perf_counter() - start
            return state, elapsed, self.cost_tracker.summary() if self.cost_tracker else {"total_cost": 0, "by_model": {}}

        state = self.prompt_agent.run(state)
        elapsed = time.perf_counter() - start

        if self.logger:
            self.logger.info("Prompt run complete in %.2fs", elapsed)
        if self.trace_recorder:
            self.trace_recorder.record(
                "complete_prompt",
                "prompt_orchestrator",
                {"history_len": len(state.history), "elapsed_sec": elapsed},
            )

        cost_summary = self.cost_tracker.summary() if self.cost_tracker else {"total_cost": 0, "by_model": {}}
        # capture final answer in state.final_answer
        return state, elapsed, cost_summary
