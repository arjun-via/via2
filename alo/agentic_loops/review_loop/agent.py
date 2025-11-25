from typing import Any, Optional

from alo.agentic_loops.core.prompts import REVIEW_PROMPT
from alo.agentic_loops.core.state import LoopState
from alo.agentic_loops.core.temperature import RECOMMENDED_TEMPERATURES


class ReviewLoopAgent:
    """Agent that reviews patches and answers for quality and correctness.

    Temperature: 0.0 (deterministic) - Code review decisions must be
    consistent and reproducible. A patch should receive the same verdict
    every time.

    Can be used in two modes:
    1. Flattened loop: Called via run() method by orchestrator
    2. Nested loop: Called via review_patch() directly by EngineeringLoopAgent
    """

    def __init__(
        self,
        model_client: Any,
        prompt_template: str | None = None,
        temperature: Optional[float] = None,
    ) -> None:
        self.model_client = model_client
        # Use structured prompt with checklist, examples, and specific criteria
        self.prompt_template = prompt_template or REVIEW_PROMPT
        # Default to recommended temperature for review role (0.0)
        self.temperature = temperature if temperature is not None else RECOMMENDED_TEMPERATURES["review"]

    def run(self, state: LoopState, tool_registry: Any | None = None) -> LoopState:
        """Standard agent interface for flattened loop mode.

        Reviews state.current_patch and sets:
        - state.review_passed: True if approved, False if rejected
        - state.review_feedback: Explanation if rejected (for retry)
        """
        if not state.current_patch:
            state.review_passed = False
            state.review_feedback = "No patch to review"
            state.add_history("review", verdict=False, feedback="No patch to review")
            return state

        prompt = self.prompt_template.format(
            issue=state.issue_description,
            patch=state.current_patch
        )
        response = self.model_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        content = str(response.get("content", ""))

        # Determine verdict
        content_upper = content.upper()
        verdict = "PASS" in content_upper and "FAIL" not in content_upper

        # Store results in state
        state.review_passed = verdict
        if not verdict:
            # Extract feedback for retry (the full response minus PASS/FAIL)
            state.review_feedback = content
        else:
            state.review_feedback = ""

        state.add_history("review", verdict=verdict, feedback=content[:200] if not verdict else "")
        return state

    def review_patch(self, state: LoopState, patch_text: str) -> bool:
        """Legacy method for nested loop mode (backward compatible).

        Called directly by EngineeringLoopAgent when using internal review.
        """
        prompt = self.prompt_template.format(issue=state.issue_description, patch=patch_text)
        response = self.model_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        content = str(response.get("content", "")).upper()
        verdict = "PASS" in content and "FAIL" not in content
        state.add_history("review", verdict=verdict)
        return verdict

    def review_answer(self, state: LoopState, answer_text: str) -> bool:
        """Review an answer (for PromptLoopAgent)."""
        prompt = (
            "You are the auditor. Review the following response for correctness, clarity, and safety. "
            "Reply with PASS if acceptable, otherwise FAIL.\n"
            f"Issue/Prompt: {state.issue_description}\n"
            f"Answer:\n{answer_text}"
        )
        response = self.model_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        content = str(response.get("content", "")).upper()
        verdict = "PASS" in content and "FAIL" not in content
        state.add_history("review", verdict=verdict)
        return verdict
