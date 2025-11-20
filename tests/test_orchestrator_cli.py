from alo.agentic_loops.core.orchestrator import ALOOrchestrator
from alo.agentic_loops.core.state import LoopState
from main import cli


class FakeContext:
    def __init__(self, name="context"):
        self.name = name
        self.calls = 0

    def run(self, state):
        self.calls += 1
        state.history.append({"step": self.name})
        state.context_summary = "ctx"
        state.relevant_files = ["file.py"]
        return state


class FakeRepro:
    def __init__(self):
        self.calls = 0

    def run(self, state):
        self.calls += 1
        state.history.append({"step": "repro"})
        state.repro_script_content = "print('fail')"
        state.repro_success = False
        return state


class FakeReview:
    def __init__(self):
        self.calls = 0
        self.verdicts = [False, True]

    def review_patch(self, state, patch_text):
        self.calls += 1
        verdict = self.verdicts.pop(0)
        state.history.append({"step": "review", "verdict": verdict})
        return verdict


class FakeEngineering:
    def __init__(self, review_agent):
        self.review_agent = review_agent
        self.calls = 0

    def run(self, state):
        self.calls += 1
        # pretend to ask review twice, then succeed
        if not self.review_agent.review_patch(state, "patch"):
            self.review_agent.review_patch(state, "patch2")
        state.repro_success = True
        state.history.append({"step": "engineering"})
        return state


def test_orchestrator_runs_pipeline():
    context = FakeContext()
    repro = FakeRepro()
    review = FakeReview()
    engineering = FakeEngineering(review)

    orch = ALOOrchestrator(
        context_agent=context,
        repro_agent=repro,
        engineering_agent=engineering,
        review_agent=review,
    )

    state = orch.run(issue_description="bug", repo_path="/repo")

    steps = [entry["step"] for entry in state.history]
    assert steps[:4] == ["context", "repro", "review", "review"]
    assert steps[-1] == "engineering"


def test_cli_invokes_orchestrator(monkeypatch, tmp_path, capsys):
    calls = {}

    class FakeOrchestrator:
        def __init__(self, *args, **kwargs):
            calls["init"] = True

        def run(self, issue_description, repo_path):
            calls["run"] = (issue_description, repo_path)
            return LoopState(issue_description=issue_description, repo_path=repo_path)

    monkeypatch.setattr("main.ALOOrchestrator", FakeOrchestrator)
    monkeypatch.setattr("main.load_config", lambda path=None: {"models": {}, "logging": {}})
    monkeypatch.setattr("main.ToolRegistry", lambda workspace_root=None: None)
    monkeypatch.setenv("PYTHONWARNINGS", "ignore")

    cli(["--issue", "bug", "--repo", str(tmp_path)])

    assert calls["run"] == ("bug", str(tmp_path))
