import logging
from typing import Any, Dict, List, Optional

from alo.backend.retry import RetryConfig, retry_with_backoff

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - openai may not be installed in tests
    OpenAI = None

logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
    """OpenAI-compatible client with retry logic for transient failures.

    Supports automatic retry with exponential backoff for:
    - Rate limit errors (429)
    - Timeout errors
    - Connection errors
    - Server errors (5xx)

    Configure retry behavior via retry_config parameter.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        extra_headers: Optional[Dict[str, str]] = None,
        extra_body: Optional[Dict[str, Any]] = None,
        client: Any | None = None,
        cost_tracker: Any | None = None,
        prompt_cost_per_1k: float | None = None,
        completion_cost_per_1k: float | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self.model = model
        self.extra_body = extra_body or {}
        self.client = client
        self.cost_tracker = cost_tracker
        self.prompt_cost_per_1k = prompt_cost_per_1k or 0.0
        self.completion_cost_per_1k = completion_cost_per_1k or 0.0
        self.retry_config = retry_config or RetryConfig()

        if self.client is None:
            if OpenAI is None:
                raise ImportError("openai package is required when no client is provided")
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                default_headers=extra_headers,
            )

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        """Send a chat completion request with automatic retry on transient failures."""
        if self.retry_config.enabled:
            return self._chat_with_retry(messages, **kwargs)
        else:
            return self._chat_impl(messages, **kwargs)

    def _chat_with_retry(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        """Chat with retry logic applied."""
        @retry_with_backoff(
            max_retries=self.retry_config.max_retries,
            initial_delay=self.retry_config.initial_delay,
            max_delay=self.retry_config.max_delay,
            exponential_base=self.retry_config.exponential_base,
            jitter=self.retry_config.jitter,
            on_retry=lambda e, attempt, delay: logger.info(
                f"[{self.model}] Retry {attempt} after {type(e).__name__}"
            ),
        )
        def _do_chat():
            return self._chat_impl(messages, **kwargs)

        return _do_chat()

    def _chat_impl(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        """Actual chat implementation without retry."""
        extra_body = kwargs.pop("extra_body", {})
        merged_extra_body = {**self.extra_body, **extra_body}
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            extra_body=merged_extra_body,
            **kwargs,
        )
        content = None
        if isinstance(response, dict):
            content = response["choices"][0]["message"]["content"]
            usage = response.get("usage", {}) or {}
        else:
            content = response.choices[0].message.content
            usage = getattr(response, "usage", {}) or {}

        if self.cost_tracker and usage:
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            if prompt_tokens is None and isinstance(usage, dict):
                prompt_tokens = usage.get("prompt_tokens", 0)
            if completion_tokens is None and isinstance(usage, dict):
                completion_tokens = usage.get("completion_tokens", 0)
            prompt_tokens = prompt_tokens or 0
            completion_tokens = completion_tokens or 0
            self.cost_tracker.record(
                model=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                prompt_cost_per_1k=self.prompt_cost_per_1k,
                completion_cost_per_1k=self.completion_cost_per_1k,
            )

        return {"content": content, "raw": response}
