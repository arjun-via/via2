from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LoopState:
    issue_description: str
    repo_path: str
    relevant_files: List[str] = field(default_factory=list)
    context_summary: str = ""
    repro_script_content: str = ""
    repro_success: Optional[bool] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    def add_history(self, step: str, **details: Any) -> None:
        self.history.append({"step": step, **details})
