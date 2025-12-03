"""
=============================================================================
SCRIPT NAME: clients.py
=============================================================================

Opus-Conductor Model Client Layer

This module provides resilient model clients with automatic failover,
retry logic, and cost tracking. All model interactions go through
the ResilientModelClient which handles provider-specific APIs.

Key Classes:
- ModelConfig: Configuration for a single model
- ResilientModelClient: Primary client with failover support
- ProviderError: Base exception for provider errors

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import os
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum

import anthropic
import openai
import google.generativeai as genai


class ProviderError(Exception):
    """Base exception for provider errors."""
    def __init__(self, message: str, provider: str, retriable: bool = True):
        super().__init__(message)
        self.provider = provider
        self.retriable = retriable


class RateLimitError(ProviderError):
    """Rate limit exceeded."""
    def __init__(self, message: str, provider: str, retry_after: float = 60.0):
        super().__init__(message, provider, retriable=True)
        self.retry_after = retry_after


class AuthenticationError(ProviderError):
    """Authentication failed - not retriable."""
    def __init__(self, message: str, provider: str):
        super().__init__(message, provider, retriable=False)


class ModelNotFoundError(ProviderError):
    """Model not found - not retriable."""
    def __init__(self, message: str, provider: str):
        super().__init__(message, provider, retriable=False)


class Provider(Enum):
    """Supported model providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    id: str
    provider: Provider
    temperature: float = 0.0
    max_tokens: int = 8192
    context_window: int = 128000
    prompt_cost_per_1k: float = 0.0
    completion_cost_per_1k: float = 0.0
    api_key_env: str = ""
    base_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], provider_config: Dict[str, Any] = None) -> "ModelConfig":
        """Create from configuration dictionary."""
        provider_str = data.get("provider", "anthropic")
        provider = Provider(provider_str)

        # Get API key env from provider config if available
        api_key_env = ""
        if provider_config:
            api_key_env = provider_config.get("api_key_env", "")

        pricing = data.get("pricing", {})

        return cls(
            id=data["id"],
            provider=provider,
            temperature=data.get("temperature", 0.0),
            max_tokens=data.get("max_tokens", 8192),
            context_window=data.get("context_window", 128000),
            prompt_cost_per_1k=pricing.get("prompt", 0.0),
            completion_cost_per_1k=pricing.get("completion", 0.0),
            api_key_env=api_key_env,
            base_url=provider_config.get("base_url") if provider_config else None,
        )


@dataclass
class ModelResponse:
    """Response from a model call."""
    content: str
    model_id: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    duration: float = 0.0
    finish_reason: str = ""
    raw_response: Any = None


@dataclass
class CostTracker:
    """Tracks costs across all model calls."""
    total_cost: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    calls_by_model: Dict[str, int] = field(default_factory=dict)
    cost_by_model: Dict[str, float] = field(default_factory=dict)

    def track(self, response: ModelResponse) -> None:
        """Track a model response."""
        self.total_cost += response.cost
        self.total_prompt_tokens += response.prompt_tokens
        self.total_completion_tokens += response.completion_tokens

        model = response.model_id
        self.calls_by_model[model] = self.calls_by_model.get(model, 0) + 1
        self.cost_by_model[model] = self.cost_by_model.get(model, 0.0) + response.cost

    def get_summary(self) -> str:
        """Get a summary of tracked costs."""
        lines = [
            f"Total Cost: ${self.total_cost:.4f}",
            f"Total Tokens: {self.total_prompt_tokens + self.total_completion_tokens:,}",
            f"  Prompt: {self.total_prompt_tokens:,}",
            f"  Completion: {self.total_completion_tokens:,}",
            "",
            "By Model:",
        ]
        for model, calls in self.calls_by_model.items():
            cost = self.cost_by_model.get(model, 0.0)
            lines.append(f"  {model}: {calls} calls, ${cost:.4f}")
        return "\n".join(lines)


class BaseProvider(ABC):
    """Abstract base class for model providers."""

    @abstractmethod
    def complete(
        self,
        messages: List[Dict[str, str]],
        model_config: ModelConfig,
        system: Optional[str] = None,
    ) -> ModelResponse:
        """Send a completion request."""
        pass


class AnthropicProvider(BaseProvider):
    """Anthropic API provider (Claude models)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise AuthenticationError("ANTHROPIC_API_KEY not set", "anthropic")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def complete(
        self,
        messages: List[Dict[str, str]],
        model_config: ModelConfig,
        system: Optional[str] = None,
    ) -> ModelResponse:
        """Send completion request to Anthropic API."""
        start_time = time.time()

        try:
            kwargs = {
                "model": model_config.id,
                "max_tokens": model_config.max_tokens,
                "temperature": model_config.temperature,
                "messages": messages,
            }
            if system:
                kwargs["system"] = system

            response = self.client.messages.create(**kwargs)

            duration = time.time() - start_time

            # Extract content
            content = ""
            if response.content:
                content = response.content[0].text if hasattr(response.content[0], 'text') else str(response.content[0])

            # Calculate cost
            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            cost = (
                (prompt_tokens / 1000) * model_config.prompt_cost_per_1k +
                (completion_tokens / 1000) * model_config.completion_cost_per_1k
            )

            return ModelResponse(
                content=content,
                model_id=model_config.id,
                provider="anthropic",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost=cost,
                duration=duration,
                finish_reason=response.stop_reason or "",
                raw_response=response,
            )

        except anthropic.RateLimitError as e:
            raise RateLimitError(str(e), "anthropic", retry_after=60.0)
        except anthropic.AuthenticationError as e:
            raise AuthenticationError(str(e), "anthropic")
        except anthropic.NotFoundError as e:
            raise ModelNotFoundError(str(e), "anthropic")
        except Exception as e:
            raise ProviderError(str(e), "anthropic")


class OpenAIProvider(BaseProvider):
    """OpenAI API provider (GPT models)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise AuthenticationError("OPENAI_API_KEY not set", "openai")
        self.client = openai.OpenAI(api_key=self.api_key, base_url=base_url)

    def complete(
        self,
        messages: List[Dict[str, str]],
        model_config: ModelConfig,
        system: Optional[str] = None,
    ) -> ModelResponse:
        """Send completion request to OpenAI API."""
        start_time = time.time()

        try:
            # Prepend system message if provided
            full_messages = []
            if system:
                full_messages.append({"role": "system", "content": system})
            full_messages.extend(messages)

            response = self.client.chat.completions.create(
                model=model_config.id,
                messages=full_messages,
                max_tokens=model_config.max_tokens,
                temperature=model_config.temperature,
            )

            duration = time.time() - start_time

            content = response.choices[0].message.content or ""
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0

            cost = (
                (prompt_tokens / 1000) * model_config.prompt_cost_per_1k +
                (completion_tokens / 1000) * model_config.completion_cost_per_1k
            )

            return ModelResponse(
                content=content,
                model_id=model_config.id,
                provider="openai",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost=cost,
                duration=duration,
                finish_reason=response.choices[0].finish_reason or "",
                raw_response=response,
            )

        except openai.RateLimitError as e:
            raise RateLimitError(str(e), "openai", retry_after=60.0)
        except openai.AuthenticationError as e:
            raise AuthenticationError(str(e), "openai")
        except openai.NotFoundError as e:
            raise ModelNotFoundError(str(e), "openai")
        except Exception as e:
            raise ProviderError(str(e), "openai")


class GoogleProvider(BaseProvider):
    """Google Generative AI provider (Gemini models)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise AuthenticationError("GEMINI_API_KEY not set", "google")
        genai.configure(api_key=self.api_key)

    def complete(
        self,
        messages: List[Dict[str, str]],
        model_config: ModelConfig,
        system: Optional[str] = None,
    ) -> ModelResponse:
        """Send completion request to Google Generative AI API."""
        start_time = time.time()

        try:
            # Create model with system instruction
            model = genai.GenerativeModel(
                model_name=model_config.id,
                system_instruction=system if system else None,
            )

            # Convert messages to Gemini format
            gemini_messages = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                gemini_messages.append({"role": role, "parts": [msg["content"]]})

            # Configure generation
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=model_config.max_tokens,
                temperature=model_config.temperature,
            )

            response = model.generate_content(
                gemini_messages,
                generation_config=generation_config,
            )

            duration = time.time() - start_time

            content = response.text if hasattr(response, 'text') else ""

            # Estimate tokens (Gemini doesn't always return exact counts)
            prompt_tokens = sum(len(msg["content"]) // 4 for msg in messages)
            completion_tokens = len(content) // 4

            cost = (
                (prompt_tokens / 1000) * model_config.prompt_cost_per_1k +
                (completion_tokens / 1000) * model_config.completion_cost_per_1k
            )

            return ModelResponse(
                content=content,
                model_id=model_config.id,
                provider="google",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost=cost,
                duration=duration,
                finish_reason="stop",
                raw_response=response,
            )

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "quota" in error_str:
                raise RateLimitError(str(e), "google", retry_after=60.0)
            if "api key" in error_str or "authentication" in error_str:
                raise AuthenticationError(str(e), "google")
            if "not found" in error_str or "does not exist" in error_str:
                raise ModelNotFoundError(str(e), "google")
            raise ProviderError(str(e), "google")


class ResilientModelClient:
    """
    Resilient model client with automatic failover and retry logic.

    This is the primary interface for all model interactions in Opus-Conductor.
    It handles:
    - Automatic failover from primary to fallback models
    - Exponential backoff retry on retriable errors
    - Cost tracking across all calls
    - Logging of all interactions
    """

    def __init__(
        self,
        primary: ModelConfig,
        fallback: Optional[ModelConfig] = None,
        cost_tracker: Optional[CostTracker] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the resilient client.

        Args:
            primary: Primary model configuration
            fallback: Fallback model configuration (optional)
            cost_tracker: Shared cost tracker instance
            max_retries: Maximum retry attempts per model
            base_delay: Base delay for exponential backoff
            max_delay: Maximum delay between retries
            logger: Logger instance
        """
        self.primary = primary
        self.fallback = fallback
        self.cost_tracker = cost_tracker or CostTracker()
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.logger = logger or logging.getLogger(__name__)

        # Initialize providers lazily
        self._providers: Dict[Provider, BaseProvider] = {}

    def _get_provider(self, provider: Provider) -> BaseProvider:
        """Get or create a provider instance."""
        if provider not in self._providers:
            if provider == Provider.ANTHROPIC:
                self._providers[provider] = AnthropicProvider()
            elif provider == Provider.OPENAI:
                self._providers[provider] = OpenAIProvider()
            elif provider == Provider.GOOGLE:
                self._providers[provider] = GoogleProvider()
            else:
                raise ValueError(f"Unknown provider: {provider}")
        return self._providers[provider]

    def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        use_fallback_on_error: bool = True,
    ) -> ModelResponse:
        """
        Send a completion request with automatic retry and failover.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            use_fallback_on_error: Whether to try fallback on primary failure

        Returns:
            ModelResponse with completion result

        Raises:
            ProviderError: If all attempts fail
        """
        # Try primary model first
        try:
            return self._complete_with_retry(self.primary, messages, system)
        except ProviderError as e:
            self.logger.warning(f"Primary model {self.primary.id} failed: {e}")

            # Try fallback if available and enabled
            if use_fallback_on_error and self.fallback:
                self.logger.info(f"Falling back to {self.fallback.id}")
                try:
                    return self._complete_with_retry(self.fallback, messages, system)
                except ProviderError as fallback_error:
                    self.logger.error(f"Fallback model {self.fallback.id} also failed: {fallback_error}")
                    raise fallback_error
            raise

    def _complete_with_retry(
        self,
        model_config: ModelConfig,
        messages: List[Dict[str, str]],
        system: Optional[str],
    ) -> ModelResponse:
        """Complete with exponential backoff retry."""
        provider = self._get_provider(model_config.provider)
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = provider.complete(messages, model_config, system)
                self.cost_tracker.track(response)
                return response

            except ProviderError as e:
                last_error = e

                if not e.retriable:
                    raise

                # Handle rate limits specially
                if isinstance(e, RateLimitError):
                    delay = e.retry_after
                else:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)

                self.logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed for {model_config.id}: {e}. "
                    f"Retrying in {delay:.1f}s"
                )
                time.sleep(delay)

        raise last_error or ProviderError("All retry attempts failed", model_config.provider.value)


class ModelClientFactory:
    """Factory for creating model clients from configuration."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize factory with configuration.

        Args:
            config: Full conductor configuration dict
        """
        self.config = config
        self._cost_tracker = CostTracker()

    @property
    def cost_tracker(self) -> CostTracker:
        """Get the shared cost tracker."""
        return self._cost_tracker

    def create_client(
        self,
        role: str,
        logger: Optional[logging.Logger] = None,
    ) -> ResilientModelClient:
        """
        Create a resilient client for a specific role.

        Args:
            role: Role name (e.g., "supervisor", "context", "engineering")
            logger: Optional logger

        Returns:
            Configured ResilientModelClient

        Raises:
            KeyError: If role not found in config
        """
        models_config = self.config.get("models", {})
        providers_config = self.config.get("providers", {})

        if role not in models_config:
            raise KeyError(f"Role '{role}' not found in model configuration")

        role_config = models_config[role]

        # Get primary model config
        primary_data = role_config.get("primary", {})
        provider_name = primary_data.get("provider", "anthropic")
        provider_config = providers_config.get(provider_name, {})
        primary = ModelConfig.from_dict(primary_data, provider_config)

        # Get fallback model config if present
        fallback = None
        if "fallback" in role_config:
            fallback_data = role_config["fallback"]
            fallback_provider = fallback_data.get("provider", "anthropic")
            fallback_provider_config = providers_config.get(fallback_provider, {})
            fallback = ModelConfig.from_dict(fallback_data, fallback_provider_config)

        # Get retry settings from orchestration config
        orch_config = self.config.get("orchestration", {})
        max_retries = orch_config.get("max_retries_per_stage", 3)

        return ResilientModelClient(
            primary=primary,
            fallback=fallback,
            cost_tracker=self._cost_tracker,
            max_retries=max_retries,
            logger=logger,
        )

    def create_all_clients(
        self,
        logger: Optional[logging.Logger] = None,
    ) -> Dict[str, ResilientModelClient]:
        """
        Create clients for all defined roles.

        Returns:
            Dict mapping role name to client
        """
        models_config = self.config.get("models", {})
        clients = {}
        for role in models_config.keys():
            clients[role] = self.create_client(role, logger)
        return clients
