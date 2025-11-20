from alo.agentic_loops.engineering_loop.agent import EngineeringLoopAgent
from alo.agentic_loops.review_loop.agent import ReviewLoopAgent
from alo.agentic_loops.core.state import LoopState
from alo.agentic_loops.core.tools import ToolRegistry


class DummyModel:
    def __init__(self, responses):
        self.responses = list(responses)

    def chat(self, messages, **kwargs):
        return {"content": self.responses.pop(0)}


def test_engineering_agent_applies_unified_diff(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "file.txt"
    target.write_text("hello\n", encoding="utf-8")

    patch_text = """\
diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@
-hello
+hello world
"""

    model = DummyModel([patch_text])
    review_model = DummyModel(["PASS"])
    agent = EngineeringLoopAgent(
        model,
        ReviewLoopAgent(review_model),
        repro_runner=lambda script: True,
        max_attempts=1,
    )
    state = LoopState(issue_description="bug", repo_path=str(repo))
    state.repro_script_content = "print('ok')"

    tools = ToolRegistry(workspace_root=repo)
    updated = agent.run(state, tool_registry=tools)

    assert "hello world" in target.read_text()
    assert updated.repro_success is True
