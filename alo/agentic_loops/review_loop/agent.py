from typing import Any

from alo.agentic_loops.core.state import LoopState


class ReviewLoopAgent:
    def __init__(self, model_client: Any, prompt_template: str | None = None) -> None:
        self.model_client = model_client
        self.prompt_template = prompt_template or (
            "Review the following patch. Reply with PASS if acceptable, otherwise FAIL.\n"
            "Issue: {issue}\nPatch:\n{patch}"
        )

    def review_patch(self, state: LoopState, patch_text: str) -> bool:
        prompt = self.prompt_template.format(issue=state.issue_description, patch=patch_text)
        response = self.model_client.chat([{"role": "user", "content": prompt}])
        content = str(response.get("content", "")).upper()
        verdict = "PASS" in content and "FAIL" not in content
        state.add_history("review", verdict=verdict)
        return verdict

    def review_answer(self, state: LoopState, answer_text: str) -> bool:
        prompt = (
            "You are the auditor. Review the following response for correctness, clarity, and safety. "
            "Reply with PASS if acceptable, otherwise FAIL.\n"
            f"Issue/Prompt: {state.issue_description}\n"
            f"Answer:\n{answer_text}"
        )
        response = self.model_client.chat([{"role": "user", "content": prompt}])
        content = str(response.get("content", "")).upper()
        verdict = "PASS" in content and "FAIL" not in content
        state.add_history("review", verdict=verdict)
        return verdict
