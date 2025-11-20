from typing import Any

from alo.agentic_loops.core.state import LoopState


class ALOOrchestrator:
    def __init__(
        self,
        context_agent: Any,
        repro_agent: Any,
        engineering_agent: Any,
        review_agent: Any,
        tool_registry: Any | None = None,
        logger: Any | None = None,
        trace_recorder: Any | None = None,
    ) -> None:
        self.context_agent = context_agent
        self.repro_agent = repro_agent
        self.engineering_agent = engineering_agent
        self.review_agent = review_agent
        self.tool_registry = tool_registry
        self.logger = logger
        self.trace_recorder = trace_recorder

    def run(self, issue_description: str, repo_path: str) -> LoopState:
        state = LoopState(issue_description=issue_description, repo_path=repo_path)
        if self.logger:
            self.logger.info("Starting ALO run")
        if self.trace_recorder:
            self.trace_recorder.record("start", "orchestrator", {"issue": issue_description})

        state = self._call_agent(self.context_agent, state, "context")
        state = self._call_agent(self.repro_agent, state, "repro")
        state = self._call_agent(self.engineering_agent, state, "engineering")

        if self.logger:
            self.logger.info("ALO run complete")
        if self.trace_recorder:
            self.trace_recorder.record("complete", "orchestrator", {"history_len": len(state.history)})

        return state

    def _call_agent(self, agent: Any, state: LoopState, name: str) -> LoopState:
        try:
            new_state = agent.run(state, self.tool_registry)
        except TypeError:
            new_state = agent.run(state)

        if self.trace_recorder:
            self.trace_recorder.record(name, getattr(agent, "__class__", type(agent)).__name__, {"history_len": len(new_state.history)})
        if self.logger:
            self.logger.info("Completed step %s", name)
        return new_state
