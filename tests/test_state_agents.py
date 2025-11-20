import json

from alo.agentic_loops.core.state import LoopState
from alo.agentic_loops.core.tools import ToolRegistry
from alo.agentic_loops.context_loop.agent import ContextLoopAgent
from alo.agentic_loops.repro_loop.agent import ReproLoopAgent
from alo.agentic_loops.review_loop.agent import ReviewLoopAgent
from alo.agentic_loops.engineering_loop.agent import EngineeringLoopAgent


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("No more responses configured")
        return {"content": self.responses.pop(0)}


def test_context_agent_updates_state():
    model = FakeModel(
        ['{"relevant_files": ["a.py", "b.py"], "summary": "found things"}']
    )
    state = LoopState(issue_description="bug", repo_path="/repo")

    agent = ContextLoopAgent(model)
    updated = agent.run(state)

    assert updated.relevant_files == ["a.py", "b.py"]
    assert updated.context_summary == "found things"
    assert updated.history[-1]["step"] == "context"


def test_repro_agent_writes_script_content():
    model = FakeModel(
        ['{"script": "print(\\"repro\\")"}']
    )
    state = LoopState(issue_description="bug", repo_path="/repo")

    agent = ReproLoopAgent(model)
    updated = agent.run(state)

    assert "repro" in updated.repro_script_content
    assert updated.repro_success is False
    assert updated.history[-1]["step"] == "repro"


def test_review_agent_records_decision():
    model = FakeModel(["PASS"])
    state = LoopState(issue_description="bug", repo_path="/repo")

    agent = ReviewLoopAgent(model)
    verdict = agent.review_patch(state, patch_text="diff --git")

    assert verdict is True
    assert state.history[-1]["step"] == "review"


def test_engineering_agent_loops_until_review_passes():
    builder_model = FakeModel(["patch1", "patch2"])
    review_model = FakeModel(["FAIL", "PASS"])

    review_agent = ReviewLoopAgent(review_model)
    state = LoopState(issue_description="bug", repo_path="/repo")
    state.repro_script_content = "print('fail')"

    def fake_repro_runner(script_text):
        return True

    agent = EngineeringLoopAgent(
        builder_model, review_agent, repro_runner=fake_repro_runner, max_attempts=2
    )
    updated = agent.run(state)

    assert len(builder_model.calls) == 2
    assert len(review_model.calls) == 2
    assert updated.repro_success is True
    assert updated.history[-1]["step"] == "engineering"


def test_engineering_agent_default_repro_runner_executes_script(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    tool_registry = ToolRegistry(workspace_root=workspace)

    builder_model = FakeModel(["patch"])
    review_model = FakeModel(["PASS"])
    review_agent = ReviewLoopAgent(review_model)
    state = LoopState(issue_description="bug", repo_path=str(workspace))
    state.repro_script_content = "print('ok')\n"

    agent = EngineeringLoopAgent(builder_model, review_agent, repro_runner=None, max_attempts=1)
    updated = agent.run(state, tool_registry=tool_registry)

    assert updated.repro_success is True
    assert (workspace / "reproduce_issue.py").exists()


def test_context_agent_fallback_collects_files_when_model_unstructured(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "alpha.py").write_text("print('alpha')\n", encoding="utf-8")

    class DummyModel:
        def chat(self, messages, **kwargs):
            return {"content": "unstructured response"}

    tool_registry = ToolRegistry(workspace_root=workspace)
    state = LoopState(issue_description="Alpha bug present", repo_path=str(workspace))
    agent = ContextLoopAgent(DummyModel())

    updated = agent.run(state, tool_registry=tool_registry)

    assert "alpha.py" in updated.relevant_files
    assert updated.history[-1]["step"] == "context"


def test_engineering_agent_writes_patch_when_tool_registry(tmp_path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    tool_registry = ToolRegistry(workspace_root=workspace)

    builder_model = FakeModel(["apply to alpha.py"])
    review_model = FakeModel(["PASS"])
    review_agent = ReviewLoopAgent(review_model)
    state = LoopState(issue_description="bug", repo_path=str(workspace))
    state.repro_script_content = "print('ok')\n"

    agent = EngineeringLoopAgent(builder_model, review_agent, repro_runner=None, max_attempts=1)
    updated = agent.run(state, tool_registry=tool_registry)

    patch_file = workspace / "applied_patch.txt"
    assert patch_file.exists()
    assert "apply to alpha.py" in patch_file.read_text()
    assert updated.repro_success is True
