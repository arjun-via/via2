from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Default maximum history size to prevent unbounded memory growth
DEFAULT_MAX_HISTORY = 100


@dataclass
class LoopState:
    """State object that flows through all agent loops.

    This dataclass accumulates context and results as it passes through
    the orchestrator pipeline: Context → Repro → Engineering → Review.

    History is automatically capped at max_history entries to prevent
    unbounded memory growth. When the limit is exceeded, oldest entries
    are removed (FIFO). A "history_truncated" marker is added to indicate
    that older entries were pruned.
    """
    issue_description: str
    repo_path: str
    relevant_files: List[str] = field(default_factory=list)
    context_summary: str = ""
    repro_script_content: str = ""
    repro_success: Optional[bool] = None
    final_answer: str = ""
    history: List[Dict[str, Any]] = field(default_factory=list)

    # Patch tracking (for flattened review loop)
    current_patch: str = ""  # Most recently generated patch
    review_passed: Optional[bool] = None  # Result of review
    review_feedback: str = ""  # Feedback from review for retry

    # History management
    max_history: int = DEFAULT_MAX_HISTORY
    _history_truncated_count: int = field(default=0, repr=False)

    def add_history(self, step: str, **details: Any) -> None:
        """Add an entry to history, pruning old entries if limit exceeded.

        When history exceeds max_history, oldest entries are removed.
        The count of truncated entries is tracked in _history_truncated_count.
        """
        self.history.append({"step": step, **details})
        self._enforce_history_limit()

    def _enforce_history_limit(self) -> None:
        """Prune history to stay within max_history limit."""
        if self.max_history <= 0:
            # Unlimited history
            return

        if len(self.history) > self.max_history:
            # Calculate how many to remove
            excess = len(self.history) - self.max_history
            self._history_truncated_count += excess

            # Remove oldest entries (keep most recent)
            self.history = self.history[excess:]

            # Add truncation marker if not already present
            if not self.history or self.history[0].get("step") != "_history_truncated":
                self.history.insert(0, {
                    "step": "_history_truncated",
                    "truncated_count": self._history_truncated_count,
                    "message": f"{self._history_truncated_count} older entries were removed to stay within limit",
                })
                # Remove one more to stay within limit after adding marker
                if len(self.history) > self.max_history:
                    self.history.pop(1)
            else:
                # Update existing truncation marker
                self.history[0]["truncated_count"] = self._history_truncated_count
                self.history[0]["message"] = f"{self._history_truncated_count} older entries were removed to stay within limit"

    def get_history_stats(self) -> Dict[str, Any]:
        """Get statistics about history including truncation info."""
        return {
            "current_size": len(self.history),
            "max_size": self.max_history,
            "truncated_count": self._history_truncated_count,
            "is_truncated": self._history_truncated_count > 0,
        }

    def clear_history(self) -> None:
        """Clear all history entries and reset truncation count."""
        self.history.clear()
        self._history_truncated_count = 0
