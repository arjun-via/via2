import json
import logging
from pathlib import Path
from typing import Any, Mapping


def init_logging(log_path: str | Path = "alo.log", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("alo")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    if not any(isinstance(h, logging.FileHandler) and str(h.baseFilename) == str(Path(log_path).resolve()) for h in logger.handlers):
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logger.level)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logger.level)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


class TraceRecorder:
    def __init__(self, trace_path: str | Path) -> None:
        self.trace_path = Path(trace_path)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, step: str, agent: str, data: Mapping[str, Any]) -> None:
        entry = {"step": step, "agent": agent, **data}
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
