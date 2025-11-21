from typing import Any

from collections import defaultdict

from alo.agentic_loops.core.state import LoopState
from alo.agentic_loops.review_loop.agent import ReviewLoopAgent


class PromptLoopAgent:
    """Generate an answer to a prompt with review/refinement loop."""

    def __init__(
        self,
        model_client: Any,
        review_agent: ReviewLoopAgent,
        max_attempts: int = 3,
        prompt_template: str | None = None,
    ) -> None:
        self.model_client = model_client
        self.review_agent = review_agent
        self.max_attempts = max_attempts
        self.prompt_template = prompt_template or (
            "You are an expert assistant. Provide the best possible answer.\n"
            "Prompt: {issue}\n"
            "Context: {context}\n"
        )

    def run(self, state: LoopState) -> LoopState:
        last_answer = ""
        for attempt in range(1, self.max_attempts + 1):
            fmt_vars = defaultdict(
                str,
                issue=state.issue_description or "",
                context=state.context_summary or "",
                files=", ".join(state.relevant_files) if state.relevant_files else "",
            )
            prompt = self.prompt_template.format_map(fmt_vars)
            try:
                response = self.model_client.chat([{"role": "user", "content": prompt}])
            except Exception as exc:
                state.add_history("prompt_error", attempt=attempt, error=str(exc))
                state.final_answer = f"Prompt run failed: {exc}"
                return state
            answer = response.get("content", "")
            last_answer = answer
            state.add_history("prompt_attempt", attempt=attempt, preview=answer[:120])

            if self.review_agent.review_answer(state, answer):
                break

        state.final_answer = last_answer
        state.add_history("prompt_result", answer_preview=last_answer[:200])
        return state
