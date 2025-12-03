"""
API client for parallel model calls.

Supports:
- Production: Claude Opus 4.5 via Anthropic
- Testing: openai/gpt-oss-120b via OpenRouter (Cerebras)
"""

import os
import asyncio
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import httpx

try:
    from .config import get_config, ModelMode, ModelConfig
except ImportError:
    from config import get_config, ModelMode, ModelConfig


@dataclass
class CompletionResult:
    """Result from a single API completion."""
    content: str
    input_tokens: int
    output_tokens: int
    cost: float
    model_id: str
    elapsed_seconds: float


class EnsembleAPIClient:
    """
    Client for making parallel API calls.

    Supports both Anthropic (Opus) and OpenRouter (test model).
    """

    def __init__(self, mode: Optional[ModelMode] = None):
        """
        Initialize the client.

        Args:
            mode: ModelMode.PRODUCTION (Opus) or ModelMode.TEST (gpt-oss-120b)
                  If None, reads from OPUS_ENSEMBLE_MODEL env var.
        """
        self.config = get_config(mode)
        self.model_config = self.config.model

        # Validate API key exists
        _ = self.model_config.api_key  # Raises if missing

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> CompletionResult:
        """
        Make a single completion request.

        Args:
            messages: List of {"role": "user/assistant", "content": "..."}
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            CompletionResult with content and usage info
        """
        temp = temperature if temperature is not None else self.model_config.temperature
        max_tok = max_tokens if max_tokens is not None else self.model_config.max_tokens

        if self.model_config.provider == "anthropic":
            return await self._complete_anthropic(messages, system_prompt, temp, max_tok)
        else:
            return await self._complete_openrouter(messages, system_prompt, temp, max_tok)

    async def complete_parallel(
        self,
        requests: List[Dict[str, Any]],
        max_concurrent: int = 10,
    ) -> List[CompletionResult]:
        """
        Make multiple completion requests in parallel.

        Args:
            requests: List of dicts with keys: messages, system_prompt, temperature, max_tokens
            max_concurrent: Max concurrent requests

        Returns:
            List of CompletionResults in same order as requests
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def limited_complete(req: Dict[str, Any]) -> CompletionResult:
            async with semaphore:
                return await self.complete(
                    messages=req.get("messages", []),
                    system_prompt=req.get("system_prompt"),
                    temperature=req.get("temperature"),
                    max_tokens=req.get("max_tokens"),
                )

        tasks = [limited_complete(req) for req in requests]
        return await asyncio.gather(*tasks)

    async def _complete_anthropic(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> CompletionResult:
        """Make request to Anthropic API."""
        start = time.time()

        headers = {
            "x-api-key": self.model_config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        body = {
            "model": self.model_config.model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        if system_prompt:
            body["system"] = system_prompt

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{self.model_config.base_url}/messages",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        elapsed = time.time() - start

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        input_tokens = data.get("usage", {}).get("input_tokens", 0)
        output_tokens = data.get("usage", {}).get("output_tokens", 0)

        cost = (
            (input_tokens / 1_000_000) * self.model_config.input_price_per_m +
            (output_tokens / 1_000_000) * self.model_config.output_price_per_m
        )

        return CompletionResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            model_id=self.model_config.model_id,
            elapsed_seconds=elapsed,
        )

    async def _complete_openrouter(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> CompletionResult:
        """Make request to OpenRouter API (OpenAI-compatible)."""
        start = time.time()

        headers = {
            "Authorization": f"Bearer {self.model_config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/via2",
            "X-Title": "Opus Ensemble",
        }

        # Build messages with system prompt
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        body = {
            "model": self.model_config.model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": all_messages,
        }

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{self.model_config.base_url}/chat/completions",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        elapsed = time.time() - start

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # gpt-oss-120b is free
        cost = (
            (input_tokens / 1_000_000) * self.model_config.input_price_per_m +
            (output_tokens / 1_000_000) * self.model_config.output_price_per_m
        )

        return CompletionResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            model_id=self.model_config.model_id,
            elapsed_seconds=elapsed,
        )


def get_client(mode: Optional[ModelMode] = None) -> EnsembleAPIClient:
    """
    Get an API client.

    Args:
        mode: ModelMode.PRODUCTION or ModelMode.TEST
              If None, reads from OPUS_ENSEMBLE_MODEL env var.
    """
    return EnsembleAPIClient(mode)
