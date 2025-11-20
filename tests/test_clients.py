from alo.backend.clients.openai_client import OpenAICompatibleClient
from alo.backend.clients.gemini_client import GeminiClient
from alo.agentic_loops.core.costs import CostTracker


def test_openai_client_passes_extra_body():
    class DummyCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return {"choices": [{"message": {"content": "ok"}}]}

    class DummyChat:
        def __init__(self):
            self.completions = DummyCompletions()

    class DummyClient:
        def __init__(self):
            self.chat = DummyChat()

    dummy = DummyClient()
    client = OpenAICompatibleClient(
        model="test-model", client=dummy, extra_body={"foo": "bar"}
    )

    response = client.chat(messages=[{"role": "user", "content": "hi"}], extra_body={"baz": "qux"})

    call = dummy.chat.completions.calls[0]
    assert call["model"] == "test-model"
    assert call["extra_body"]["foo"] == "bar"
    assert call["extra_body"]["baz"] == "qux"
    assert response["content"] == "ok"


def test_gemini_client_uses_model_and_key():
    class DummyResult:
        def __init__(self):
            self.text = "gemini-response"

    class DummyModel:
        def __init__(self):
            self.calls = []

        def generate_content(self, prompt, **kwargs):
            self.calls.append((prompt, kwargs))
            return DummyResult()

    class DummyGenAI:
        def __init__(self):
            self.models = []
            self.last_key = None
            self.model = DummyModel()

        def configure(self, api_key=None):
            self.last_key = api_key

        def GenerativeModel(self, model_name):
            self.models.append(model_name)
            return self.model

    dummy_genai = DummyGenAI()
    client = GeminiClient(model="gemini-3", api_key="test-key", genai=dummy_genai)

    result = client.generate(prompt="hello")

    assert dummy_genai.last_key == "test-key"
    assert dummy_genai.models == ["gemini-3"]
    assert dummy_genai.model.calls[0][0] == "hello"
    assert result == "gemini-response"


def test_openai_client_records_costs_with_usage_and_pricing():
    tracker = CostTracker.get_instance()
    tracker.reset()

    class DummyResponse:
        def __init__(self):
            self.choices = [
                type("c", (), {"message": type("m", (), {"content": "ok"})()})
            ]
            self.usage = {"prompt_tokens": 10, "completion_tokens": 5}

    class DummyCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return DummyResponse()

    class DummyChat:
        def __init__(self):
            self.completions = DummyCompletions()

    class DummyClient:
        def __init__(self):
            self.chat = DummyChat()

    client = OpenAICompatibleClient(
        model="cost-model",
        client=DummyClient(),
        cost_tracker=tracker,
        prompt_cost_per_1k=1.0,
        completion_cost_per_1k=2.0,
    )

    _ = client.chat([{"role": "user", "content": "hi"}])

    summary = tracker.summary()
    assert summary["by_model"]["cost-model"]["prompt_tokens"] == 10
    assert summary["by_model"]["cost-model"]["completion_tokens"] == 5
    assert summary["by_model"]["cost-model"]["cost"] == (10 / 1000) * 1.0 + (5 / 1000) * 2.0
