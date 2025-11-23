"""Base runner interface for benchmark systems."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class RunResult:
    """Result from running a system on a prompt."""
    output: str
    elapsed_time: float  # seconds
    cost: float  # USD
    metadata: Dict[str, Any]
    context_used: Optional[str] = None


class BaseRunner(ABC):
    """Abstract base class for all system runners."""

    @abstractmethod
    def run(self, prompt: str, context: Optional[str] = None) -> RunResult:
        """
        Run the system on a given prompt.

        Args:
            prompt: The task/question to execute
            context: Optional context (repo summary, relevant files, etc.)

        Returns:
            RunResult with output, metrics, and metadata
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this runner."""
        pass
