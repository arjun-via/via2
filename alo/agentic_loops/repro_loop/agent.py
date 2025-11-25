import json
from typing import Any, Dict, Optional

from alo.agentic_loops.core.prompts import REPRO_PROMPT
from alo.agentic_loops.core.state import LoopState
from alo.agentic_loops.core.temperature import RECOMMENDED_TEMPERATURES


class ReproLoopAgent:
    """Agent that generates reproduction scripts for issues.

    Temperature: 0.0 (deterministic) - Reproduction scripts must be
    syntactically correct and precisely test the described behavior.
    """

    def __init__(
        self,
        model_client: Any,
        prompt_template: str | None = None,
        temperature: Optional[float] = None,
    ) -> None:
        self.model_client = model_client
        # Use structured prompt with JSON schema, template, and examples
        self.prompt_template = prompt_template or REPRO_PROMPT
        # Default to recommended temperature for repro role (0.0)
        self.temperature = temperature if temperature is not None else RECOMMENDED_TEMPERATURES["repro"]

    def run(self, state: LoopState, tool_registry: Any | None = None) -> LoopState:
        prompt = self.prompt_template.format(issue=state.issue_description)
        response = self.model_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
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
