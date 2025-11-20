import json
from typing import Any, Dict, List

from alo.agentic_loops.core.state import LoopState


class ContextLoopAgent:
    def __init__(self, model_client: Any, prompt_template: str | None = None) -> None:
        self.model_client = model_client
        self.prompt_template = prompt_template or (
            "You are the context librarian. Given an issue description, propose relevant files "
            "and a short context summary as JSON with keys relevant_files and summary.\n"
            "Issue: {issue}"
        )

    def run(self, state: LoopState, tool_registry: Any | None = None) -> LoopState:
        prompt = self.prompt_template.format(issue=state.issue_description)
        response = self.model_client.chat([{"role": "user", "content": prompt}])
        content = response.get("content", "")
        parsed = _parse_context_response(content)
        model_files = parsed.get("relevant_files", [])
        state.context_summary = parsed.get("summary", content)

        tool_files = []
        if tool_registry is not None:
            tool_files = _find_relevant_files(state.issue_description, tool_registry)

        state.relevant_files = list(dict.fromkeys(model_files + tool_files))
        state.add_history("context", relevant_files=state.relevant_files, summary=state.context_summary)
        return state


def _parse_context_response(content: str) -> Dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        files: List[str] = []
        summary = content.strip()
        return {"relevant_files": files, "summary": summary}


def _find_relevant_files(issue: str, tool_registry: Any) -> List[str]:
    keywords = [word.lower() for word in issue.split() if len(word) > 2]
    matches: List[str] = []
    try:
        for path in tool_registry.list_files():
            lower_path = path.lower()
            if any(k in lower_path for k in keywords):
                matches.append(path)
    except Exception:
        return []
    return matches
