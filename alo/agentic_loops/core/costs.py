import threading
from collections import defaultdict
from typing import Dict


class CostTracker:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
        )

    @classmethod
    def get_instance(cls) -> "CostTracker":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def reset(self) -> None:
        with self._lock:
            self._data.clear()

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        prompt_cost_per_1k: float,
        completion_cost_per_1k: float,
    ) -> None:
        prompt_cost = (prompt_tokens / 1000) * prompt_cost_per_1k
        completion_cost = (completion_tokens / 1000) * completion_cost_per_1k
        with self._lock:
            entry = self._data[model]
            entry["prompt_tokens"] += prompt_tokens
            entry["completion_tokens"] += completion_tokens
            entry["cost"] += prompt_cost + completion_cost

    def summary(self) -> Dict[str, Dict]:
        with self._lock:
            by_model = {k: dict(v) for k, v in self._data.items()}
            total_cost = sum(v["cost"] for v in self._data.values())
            return {"by_model": by_model, "total_cost": total_cost}
