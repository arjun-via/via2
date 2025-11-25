import logging
from typing import Any

from alo.backend.retry import RetryConfig, retry_with_backoff

try:
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover - optional dependency for tests
    genai = None

logger = logging.getLogger(__name__)


class GeminiClient:
    """Gemini client with retry logic for transient failures.

    Supports automatic retry with exponential backoff for:
    - Rate limit errors (ResourceExhausted)
    - Timeout errors
    - Connection errors
    - Server errors
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        genai: Any | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self._genai = genai or globals().get("genai")
        if self._genai is None:
            raise ImportError("google-generativeai is required when no client is provided")
        self._genai.configure(api_key=api_key)
        self.model = self._genai.GenerativeModel(model)
        self.model_name = model
        self.retry_config = retry_config or RetryConfig()

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate content with automatic retry on transient failures."""
        if self.retry_config.enabled:
            return self._generate_with_retry(prompt, **kwargs)
        else:
            return self._generate_impl(prompt, **kwargs)

    def _generate_with_retry(self, prompt: str, **kwargs: Any) -> str:
        """Generate with retry logic applied."""
        @retry_with_backoff(
            max_retries=self.retry_config.max_retries,
            initial_delay=self.retry_config.initial_delay,
            max_delay=self.retry_config.max_delay,
            exponential_base=self.retry_config.exponential_base,
            jitter=self.retry_config.jitter,
            on_retry=lambda e, attempt, delay: logger.info(
                f"[{self.model_name}] Retry {attempt} after {type(e).__name__}"
            ),
        )
        def _do_generate():
            return self._generate_impl(prompt, **kwargs)

        return _do_generate()

    def _generate_impl(self, prompt: str, **kwargs: Any) -> str:
        """Actual generate implementation without retry."""
        result = self.model.generate_content(prompt, **kwargs)
        if hasattr(result, "text"):
            return result.text
        return str(result)

    def chat(self, messages, **kwargs: Any) -> dict:
        """Provide chat-like interface to align with other clients."""
        prompt_parts = []
        for msg in messages:
            content = msg.get("content", "")
            prompt_parts.append(str(content))
        prompt = "\n".join(prompt_parts)
        text = self.generate(prompt, **kwargs)
        return {"content": text}
