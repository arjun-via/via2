import json
import logging
from pathlib import Path

from alo.agentic_loops.core.logging_utils import TraceRecorder, init_logging


def test_init_logging_and_trace_recorder(tmp_path):
    log_path = tmp_path / "alo.log"
    trace_path = tmp_path / "trace.jsonl"

    logger = init_logging(log_path=log_path, level="DEBUG")
    logger.debug("debug message")
    logger.info("info message")

    assert log_path.exists()
    log_content = log_path.read_text()
    assert "debug message" in log_content

    recorder = TraceRecorder(trace_path)
    recorder.record(step="context", agent="librarian", data={"msg": "hi"})
    recorder.record(step="repro", agent="scientist", data={"ok": True})

    lines = trace_path.read_text().splitlines()
    assert len(lines) == 2
    entry = json.loads(lines[0])
    assert entry["step"] == "context"
    assert entry["agent"] == "librarian"

