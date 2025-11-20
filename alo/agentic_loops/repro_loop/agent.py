import json
from typing import Any, Dict

from alo.agentic_loops.core.state import LoopState


class ReproLoopAgent:
    def __init__(self, model_client: Any, prompt_template: str | None = None) -> None:
        self.model_client = model_client
        self.prompt_template = prompt_template or (
            'Write a Python reproduction script for the issue as JSON {{"script": "..."}}.\nIssue: {issue}'
        )

    def run(self, state: LoopState, tool_registry: Any | None = None) -> LoopState:
        prompt = self.prompt_template.format(issue=state.issue_description)
        response = self.model_client.chat([{"role": "user", "content": prompt}])
        content = response.get("content", "")
        script = _extract_script(content)
        state.repro_script_content = script
        state.repro_success = False
        state.add_history("repro", script_present=bool(script))
        return state


def _extract_script(content: str) -> str:
    try:
        parsed: Dict[str, str] = json.loads(content)
        return parsed.get("script", content)
    except json.JSONDecodeError:
        return content
