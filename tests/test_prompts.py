from alo.agentic_loops.context_loop.agent import ContextLoopAgent
from alo.agentic_loops.repro_loop.agent import ReproLoopAgent
from alo.agentic_loops.core.state import LoopState


class CapturingModel:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(messages)
        return {"content": self.response}


def test_context_agent_uses_custom_prompt():
    model = CapturingModel('{"relevant_files": [], "summary": "ok"}')
    prompt = "CUSTOM CONTEXT PROMPT: {issue}"
    agent = ContextLoopAgent(model_client=model, prompt_template=prompt)

    state = LoopState(issue_description="ISSUE TEXT", repo_path="/repo")
    agent.run(state=state, tool_registry=None)

    sent = model.calls[0][0]["content"]
    assert "CUSTOM CONTEXT PROMPT" in sent


def test_repro_agent_uses_custom_prompt():
    model = CapturingModel('{"script": "print(1)"}')
    prompt = "CUSTOM REPRO PROMPT: {issue}"
    agent = ReproLoopAgent(model_client=model, prompt_template=prompt)

    state = LoopState(issue_description="ISSUE TEXT", repo_path="/repo")
    agent.run(state=state, tool_registry=None)

    sent = model.calls[0][0]["content"]
    assert "CUSTOM REPRO PROMPT" in sent
