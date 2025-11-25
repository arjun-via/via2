import inspect
from typing import Any

from alo.agentic_loops.core.exceptions import AgentExecutionError
from alo.agentic_loops.core.state import LoopState


class ALOOrchestrator:
    """Main orchestrator coordinating all agent loops.

    Supports two review modes:
    1. Nested (default, backward compatible): Engineering handles review internally
    2. Flattened: Engineering-Review loop managed at orchestrator level

    Set use_flattened_review=True for explicit control flow visibility.
    """

    def __init__(
        self,
        context_agent: Any,
        repro_agent: Any,
        engineering_agent: Any,
        review_agent: Any,
        tool_registry: Any | None = None,
        logger: Any | None = None,
        trace_recorder: Any | None = None,
        use_flattened_review: bool = False,
        max_review_attempts: int = 3,
    ) -> None:
        self.context_agent = context_agent
        self.repro_agent = repro_agent
        self.engineering_agent = engineering_agent
        self.review_agent = review_agent
        self.tool_registry = tool_registry
        self.logger = logger
        self.trace_recorder = trace_recorder
        self.use_flattened_review = use_flattened_review
        self.max_review_attempts = max_review_attempts

    def run(self, issue_description: str, repo_path: str) -> LoopState:
        state = LoopState(issue_description=issue_description, repo_path=repo_path)
        if self.logger:
            self.logger.info("Starting ALO run")
        if self.trace_recorder:
            self.trace_recorder.record("start", "orchestrator", {"issue": issue_description})

        # Context and Repro are always sequential
        state = self._call_agent(self.context_agent, state, "context")
        state = self._call_agent(self.repro_agent, state, "repro")

        if self.use_flattened_review:
            # Flattened mode: Engineering-Review loop at orchestrator level
            state = self._run_engineering_review_loop(state)
        else:
            # Nested mode: Engineering handles review internally (backward compatible)
            state = self._call_agent(self.engineering_agent, state, "engineering")

        if self.logger:
            self.logger.info("ALO run complete")
        if self.trace_recorder:
            self.trace_recorder.record("complete", "orchestrator", {
                "history_len": len(state.history),
                "review_mode": "flattened" if self.use_flattened_review else "nested",
            })

        return state

    def _run_engineering_review_loop(self, state: LoopState) -> LoopState:
        """Engineering-Review loop at orchestrator level.

        This provides:
        - Full visibility into the loop at orchestrator level
        - Easy A/B testing of different review strategies
        - Clear separation of concerns
        - Review feedback passed to engineering for retry
        """
        for attempt in range(1, self.max_review_attempts + 1):
            if self.logger:
                self.logger.info(f"Engineering-Review attempt {attempt}/{self.max_review_attempts}")
            if self.trace_recorder:
                self.trace_recorder.record("engineering_review_attempt", "orchestrator", {"attempt": attempt})

            # Engineering generates patch
            state = self._call_agent(self.engineering_agent, state, "engineering")

            # Check if repro passed
            if not state.repro_success:
                if self.logger:
                    self.logger.warning(f"Attempt {attempt}: Repro failed, retrying...")
                state.review_feedback = "Reproduction script failed. The fix did not resolve the issue."
                continue

            # Review the patch
            state = self._call_agent(self.review_agent, state, "review")

            # Check if review passed
            if state.review_passed:
                if self.logger:
                    self.logger.info(f"Attempt {attempt}: Review passed!")
                break
            else:
                if self.logger:
                    self.logger.warning(f"Attempt {attempt}: Review failed, retrying...")
                # review_feedback already set by ReviewLoopAgent.run()

        # Record final status
        state.add_history(
            "engineering_review_loop",
            attempts=attempt,
            final_repro_success=state.repro_success,
            final_review_passed=state.review_passed,
        )

        return state

    def _call_agent(self, agent: Any, state: LoopState, name: str) -> LoopState:
        """Call an agent's run method with proper signature detection.

        FAIL IS FAIL policy: We use introspection to determine the correct
        signature upfront rather than catching TypeErrors. Real TypeErrors
        in agent code are now surfaced properly.
        """
        try:
            # Introspect the agent's run method to determine correct signature
            run_method = getattr(agent, "run", None)
            if run_method is None:
                raise AgentExecutionError(name, AttributeError("Agent has no 'run' method"))

            sig = inspect.signature(run_method)
            params = list(sig.parameters.keys())

            # Determine if agent accepts tool_registry (has 2+ params after self)
            # Parameters: 'state' is required, 'tool_registry' is optional
            accepts_tool_registry = len(params) >= 2 and "tool_registry" in params

            if accepts_tool_registry:
                new_state = agent.run(state, self.tool_registry)
            else:
                new_state = agent.run(state)

        except AgentExecutionError:
            raise  # Re-raise our own errors
        except Exception as e:
            raise AgentExecutionError(name, e) from e

        if self.trace_recorder:
            self.trace_recorder.record(name, getattr(agent, "__class__", type(agent)).__name__, {"history_len": len(new_state.history)})
        if self.logger:
            self.logger.info("Completed step %s", name)
        return new_state
