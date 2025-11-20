import json
from pathlib import Path

from alo.agentic_loops.context_loop.agent import ContextLoopAgent
from alo.agentic_loops.core.orchestrator import ALOOrchestrator
from alo.agentic_loops.core.tools import ToolRegistry
from alo.agentic_loops.engineering_loop.agent import EngineeringLoopAgent
from alo.agentic_loops.repro_loop.agent import ReproLoopAgent
from alo.agentic_loops.review_loop.agent import ReviewLoopAgent


class StubModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(messages)
        return {"content": self.responses.pop(0)}


def test_full_loop_with_tools(tmp_path):
    repo = tmp_path / "sample"
    repo.mkdir()
    (repo / "bug.py").write_text("print('bug')\n", encoding="utf-8")

    context_model = StubModel(
        ['{"relevant_files": ["bug.py"], "summary": "bug file"}']
    )
    repro_model = StubModel(['{"script": "print(\\"ok\\")"}'])
    engineering_model = StubModel(["apply fix to bug.py"])
    review_model = StubModel(["PASS"])

    context_agent = ContextLoopAgent(context_model)
    repro_agent = ReproLoopAgent(repro_model)
    review_agent = ReviewLoopAgent(review_model)
    engineering_agent = EngineeringLoopAgent(engineering_model, review_agent, repro_runner=None)

    tool_registry = ToolRegistry(workspace_root=repo)
    orch = ALOOrchestrator(
        context_agent=context_agent,
        repro_agent=repro_agent,
        engineering_agent=engineering_agent,
        review_agent=review_agent,
        tool_registry=tool_registry,
    )

    state = orch.run(issue_description="bug in bug.py", repo_path=str(repo))

    # Patch and repro artifacts created
    assert (repo / "applied_patch.txt").exists()
    assert "bug.py" in (repo / "applied_patch.txt").read_text()
    assert (repo / "reproduce_issue.py").exists()

    # LoopState reflects steps
    steps = [entry["step"] for entry in state.history]
    assert "context" in steps and "repro" in steps and "engineering" in steps
