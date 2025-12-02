"""
=============================================================================
SCRIPT NAME: multi_provider_client.py
=============================================================================

Multi-Provider Client for Opus Meta-Orchestrator.
Unified interface for all model providers.

INPUT FILES:
- Environment variables for API keys

OUTPUT FILES:
- None (API client)

VERSION: 1.1
LAST UPDATED: 2025-11-28

DESCRIPTION:
Provides a unified client interface that can call any LLM provider
(Cerebras, Groq, OpenAI, OpenRouter, Google Native) using the same API.

DEPENDENCIES:
- requests
- time (standard library)
- google-genai (for Google Native provider)

=============================================================================
"""

from typing import Dict, List, Optional, Any
import requests
import time
from dataclasses import dataclass

from .model_registry import ModelConfig, Provider

# Lazy import for Google genai SDK
_google_genai_client = None


@dataclass
class CompletionResult:
    """Result from a model completion."""
    content: str
    input_tokens: int
    output_tokens: int
    elapsed_time: float
    tokens_per_second: float
    cost: float
    model: str
    provider: str


class MultiProviderClient:
    """
    Unified client for all model providers.

    Supports:
    - Cerebras (native API)
    - Groq (native API)
    - OpenAI (native API)
    - OpenRouter (proxy for premium models)
    - Google Native (direct Gemini API via google-genai SDK)
    """

    def __init__(self, cost_tracker=None):
        """
        Initialize the multi-provider client.

        Args:
            cost_tracker: Optional CostTracker instance for usage tracking
        """
        self.cost_tracker = cost_tracker
        self._google_client = None

    def _get_google_client(self, api_key: str):
        """Lazy initialize Google genai client."""
        if self._google_client is None:
            from google import genai
            self._google_client = genai.Client(api_key=api_key)
        return self._google_client

    def complete(
        self,
        model_config: ModelConfig,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0,
        **kwargs
    ) -> CompletionResult:
        """
        Send completion request to any provider.

        Args:
            model_config: Model configuration from registry
            messages: Chat messages in OpenAI format
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            CompletionResult with response and metrics

        Raises:
            Exception: If API call fails
        """
        # Handle Google Native provider separately
        if model_config.provider == Provider.GOOGLE_NATIVE:
            return self._complete_google_native(
                model_config, messages, max_tokens, temperature
            )

        headers = self._get_headers(model_config)
        payload = self._build_payload(model_config, messages, max_tokens, temperature)

        start_time = time.time()

        response = requests.post(
            f"{model_config.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=300
        )

        elapsed_time = time.time() - start_time

        if response.status_code != 200:
            raise Exception(
                f"API Error {response.status_code} from {model_config.provider.value}: "
                f"{response.text[:500]}"
            )

        data = response.json()

        # Extract response
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # Calculate metrics
        tokens_per_second = output_tokens / elapsed_time if elapsed_time > 0 else 0
        cost = (
            (input_tokens / 1_000_000) * model_config.input_price_per_m +
            (output_tokens / 1_000_000) * model_config.output_price_per_m
        )

        # Track costs if tracker provided
        if self.cost_tracker:
            self.cost_tracker.track_usage(
                model=model_config.id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost
            )

        return CompletionResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            elapsed_time=elapsed_time,
            tokens_per_second=tokens_per_second,
            cost=cost,
            model=model_config.id,
            provider=model_config.provider.value
        )

    def _complete_google_native(
        self,
        model_config: ModelConfig,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float
    ) -> CompletionResult:
        """
        Handle Google Native (Gemini) API calls using google-genai SDK.

        Args:
            model_config: Model configuration (must be GOOGLE_NATIVE provider)
            messages: Chat messages in OpenAI format
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            CompletionResult with response and metrics
        """
        from google.genai import types

        api_key = model_config.get_api_key()
        client = self._get_google_client(api_key)

        # Convert OpenAI message format to Gemini format
        # Gemini expects a simple string or list of content parts
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Gemini uses "user" and "model" roles
            gemini_role = "model" if role == "assistant" else "user"
            contents.append(types.Content(
                role=gemini_role,
                parts=[types.Part(text=content)]
            ))

        # If only one message (common case), just use the text
        if len(messages) == 1:
            contents = messages[0].get("content", "")

        start_time = time.time()

        response = client.models.generate_content(
            model=model_config.id,  # e.g., "gemini-3-pro-preview"
            contents=contents,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                # Gemini 3 Pro has thinking - set include_thoughts=False to get text output
                thinking_config=types.ThinkingConfig(include_thoughts=False)
            )
        )

        elapsed_time = time.time() - start_time

        # Extract text from response
        content = response.text if hasattr(response, 'text') and response.text else ""

        # Get token counts from usage metadata
        usage = getattr(response, 'usage_metadata', None)
        input_tokens = getattr(usage, 'prompt_token_count', 0) if usage else 0
        output_tokens = getattr(usage, 'candidates_token_count', 0) if usage else 0
        # Ensure tokens are integers (not None)
        input_tokens = input_tokens or 0
        output_tokens = output_tokens or 0

        # Calculate metrics
        tokens_per_second = output_tokens / elapsed_time if elapsed_time > 0 else 0
        cost = (
            (input_tokens / 1_000_000) * model_config.input_price_per_m +
            (output_tokens / 1_000_000) * model_config.output_price_per_m
        )

        # Track costs if tracker provided
        if self.cost_tracker:
            self.cost_tracker.track_usage(
                model=model_config.id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost
            )

        return CompletionResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            elapsed_time=elapsed_time,
            tokens_per_second=tokens_per_second,
            cost=cost,
            model=model_config.id,
            provider=model_config.provider.value
        )

    def _get_headers(self, model_config: ModelConfig) -> Dict[str, str]:
        """
        Get headers for provider.

        Args:
            model_config: Model configuration

        Returns:
            Dict of HTTP headers
        """
        api_key = model_config.get_api_key()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # OpenRouter specific headers
        if model_config.provider == Provider.OPENROUTER:
            headers["HTTP-Referer"] = "https://github.com/alo-orchestrator"
            headers["X-Title"] = "ALO Opus Meta-Orchestrator"

        return headers

    def _build_payload(
        self,
        model_config: ModelConfig,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """
        Build request payload for provider.

        Args:
            model_config: Model configuration
            messages: Chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Dict payload for API request
        """
        payload = {
            "model": model_config.id,
            "messages": messages,
            "temperature": temperature
        }

        # Different providers use different token limit params
        if model_config.provider == Provider.OPENAI:
            # GPT-5.x uses max_completion_tokens
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens

        return payload

    def complete_with_retry(
        self,
        model_config: ModelConfig,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0,
        max_retries: int = 3,
        **kwargs
    ) -> CompletionResult:
        """
        Send completion request with automatic retry on failure.

        Args:
            model_config: Model configuration from registry
            messages: Chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            max_retries: Maximum retry attempts

        Returns:
            CompletionResult with response and metrics

        Raises:
            Exception: If all retries fail
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return self.complete(
                    model_config=model_config,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)

        raise Exception(f"All {max_retries} attempts failed. Last error: {last_error}")
