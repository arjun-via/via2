"""
=============================================================================
ALO v2.0 Model Clients
=============================================================================

Unified client interfaces for all models in the pipeline.

CLIENTS:
- AnthropicClient: For Opus orchestrator (claude-opus-4-5-20251101)
- OpenRouterClient: For workers (Kimi K2, Gemini 3 Flash via OpenRouter)

All clients share a common interface:
    response = client.generate(messages, system_prompt=None, max_tokens=4096)
=============================================================================
"""

import time
import httpx
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional

from .config import ModelConfig


@dataclass
class ModelResponse:
    """Standardized response from any model"""
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    cost: float  # Estimated cost in dollars


class BaseClient(ABC):
    """Base class for all model clients"""

    def __init__(self, config: ModelConfig, api_key: str):
        self.config = config
        self.api_key = api_key

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> ModelResponse:
        """Generate a response from the model"""
        pass

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on token usage (pricing is per 1M tokens)"""
        prompt_cost = (prompt_tokens / 1_000_000) * self.config.pricing_prompt
        completion_cost = (completion_tokens / 1_000_000) * self.config.pricing_completion
        return prompt_cost + completion_cost


class AnthropicClient(BaseClient):
    """Client for Anthropic's Claude models (Opus orchestrator)"""

    def __init__(self, config: ModelConfig, api_key: str):
        super().__init__(config, api_key)
        self.base_url = "https://api.anthropic.com/v1"

    def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> ModelResponse:
        """Generate response from Claude"""

        start_time = time.time()

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": self.config.model_id,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "messages": messages
        }

        if system_prompt:
            payload["system"] = system_prompt

        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = (time.time() - start_time) * 1000

        content = data["content"][0]["text"] if data["content"] else ""
        prompt_tokens = data["usage"]["input_tokens"]
        completion_tokens = data["usage"]["output_tokens"]

        return ModelResponse(
            content=content,
            model=self.config.model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            cost=self._calculate_cost(prompt_tokens, completion_tokens)
        )


class OpenRouterClient(BaseClient):
    """Client for OpenRouter models (Kimi K2, Gemini 3 Flash workers)"""

    def __init__(self, config: ModelConfig, api_key: str):
        super().__init__(config, api_key)
        self.base_url = config.base_url or "https://openrouter.ai/api/v1"

    def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> ModelResponse:
        """Generate response from OpenRouter model"""

        start_time = time.time()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/via2-alo",
            "X-Title": "ALO v2"
        }

        # Prepend system message if provided
        all_messages = messages.copy()
        if system_prompt:
            all_messages = [{"role": "system", "content": system_prompt}] + all_messages

        payload = {
            "model": self.config.model_id,
            "messages": all_messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature
        }

        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = (time.time() - start_time) * 1000

        content = data["choices"][0]["message"]["content"] if data["choices"] else ""
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        return ModelResponse(
            content=content,
            model=self.config.model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            cost=self._calculate_cost(prompt_tokens, completion_tokens)
        )


class ClientFactory:
    """Factory for creating model clients"""

    @staticmethod
    def create(config: ModelConfig, api_key: str) -> BaseClient:
        """Create appropriate client based on provider"""

        if config.provider == "anthropic":
            return AnthropicClient(config, api_key)
        elif config.provider == "openrouter":
            return OpenRouterClient(config, api_key)
        else:
            raise ValueError(f"Unknown provider: {config.provider}")


def test_clients():
    """Quick test of all clients"""
    from .config import Config

    config = Config()
    if not config.validate():
        print("Configuration validation failed")
        return

    test_messages = [{"role": "user", "content": "Say 'Hello ALO v2' in exactly 3 words."}]

    # Test Opus
    print("\nTesting Opus (orchestrator)...")
    opus_client = ClientFactory.create(config.get_model("opus"), config.anthropic_api_key)
    response = opus_client.generate(test_messages)
    print(f"   Response: {response.content[:100]}")
    print(f"   Tokens: {response.total_tokens}, Latency: {response.latency_ms:.0f}ms, Cost: ${response.cost:.4f}")

    # Test Kimi K2
    print("\nTesting Kimi K2 (worker)...")
    kimi_client = ClientFactory.create(config.get_model("kimi-k2"), config.openrouter_api_key)
    response = kimi_client.generate(test_messages)
    print(f"   Response: {response.content[:100]}")
    print(f"   Tokens: {response.total_tokens}, Latency: {response.latency_ms:.0f}ms, Cost: ${response.cost:.6f}")

    # Test Gemini 3 Flash (via OpenRouter)
    print("\nTesting Gemini 3 Flash (worker via OpenRouter)...")
    gemini_client = ClientFactory.create(config.get_model("gemini-3-flash"), config.openrouter_api_key)
    response = gemini_client.generate(test_messages)
    print(f"   Response: {response.content[:100]}")
    print(f"   Tokens: {response.total_tokens}, Latency: {response.latency_ms:.0f}ms, Cost: ${response.cost:.6f}")

    print("\nAll clients working!")


if __name__ == "__main__":
    test_clients()
