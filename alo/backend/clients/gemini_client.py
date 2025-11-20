from typing import Any

try:
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover - optional dependency for tests
    genai = None


class GeminiClient:
    def __init__(self, model: str, api_key: str, genai: Any | None = None) -> None:
        self._genai = genai or globals().get("genai")
        if self._genai is None:
            raise ImportError("google-generativeai is required when no client is provided")
        self._genai.configure(api_key=api_key)
        self.model = self._genai.GenerativeModel(model)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        result = self.model.generate_content(prompt, **kwargs)
        if hasattr(result, "text"):
            return result.text
        return str(result)

    # Provide chat-like interface to align with other clients
    def chat(self, messages, **kwargs: Any) -> dict:
        # flatten messages into a single prompt
        prompt_parts = []
        for msg in messages:
            content = msg.get("content", "")
            prompt_parts.append(str(content))
        prompt = "\n".join(prompt_parts)
        text = self.generate(prompt, **kwargs)
        return {"content": text}
