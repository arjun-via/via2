"""
Tests for api_client.py - API client for model calls.
"""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_client import EnsembleAPIClient, CompletionResult, get_client
from config import ModelMode


class TestCompletionResult:
    """Tests for CompletionResult dataclass."""

    def test_create_result(self):
        """Create a CompletionResult."""
        result = CompletionResult(
            content="Hello, world!",
            input_tokens=10,
            output_tokens=5,
            cost=0.001,
            model_id="test-model",
            elapsed_seconds=0.5,
        )
        assert result.content == "Hello, world!"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.cost == 0.001


class TestEnsembleAPIClient:
    """Tests for EnsembleAPIClient class."""

    def test_init_test_mode(self):
        """Initialize client in test mode."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123"}):
            client = EnsembleAPIClient(mode=ModelMode.TEST)
            assert client.model_config.model_id == "openai/gpt-oss-120b"
            assert client.model_config.provider == "openrouter"

    def test_init_production_mode(self):
        """Initialize client in production mode."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"}):
            client = EnsembleAPIClient(mode=ModelMode.PRODUCTION)
            assert client.model_config.model_id == "claude-opus-4-5-20251101"
            assert client.model_config.provider == "anthropic"

    def test_missing_api_key_raises(self):
        """Missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENROUTER_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with pytest.raises(ValueError, match="Missing API key"):
                EnsembleAPIClient(mode=ModelMode.TEST)


class TestCompleteMethod:
    """Tests for complete method."""

    @pytest.mark.asyncio
    async def test_complete_openrouter(self):
        """Complete request to OpenRouter."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            client = EnsembleAPIClient(mode=ModelMode.TEST)

            # Mock httpx response
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test response"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            }
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_class.return_value = mock_client

                result = await client.complete(
                    messages=[{"role": "user", "content": "Hello"}]
                )

            assert result.content == "Test response"
            assert result.input_tokens == 100
            assert result.output_tokens == 50
            assert result.cost == 0.0  # Free model

    @pytest.mark.asyncio
    async def test_complete_anthropic(self):
        """Complete request to Anthropic."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = EnsembleAPIClient(mode=ModelMode.PRODUCTION)

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "content": [{"type": "text", "text": "Anthropic response"}],
                "usage": {"input_tokens": 100, "output_tokens": 200},
            }
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_class.return_value = mock_client

                result = await client.complete(
                    messages=[{"role": "user", "content": "Hello"}]
                )

            assert result.content == "Anthropic response"
            assert result.input_tokens == 100
            assert result.output_tokens == 200
            # Cost: (100/1M * 5) + (200/1M * 25) = 0.0005 + 0.005 = 0.0055
            expected_cost = (100 / 1_000_000) * 5.0 + (200 / 1_000_000) * 25.0
            assert abs(result.cost - expected_cost) < 0.0001


class TestCompleteParallel:
    """Tests for complete_parallel method."""

    @pytest.mark.asyncio
    async def test_parallel_requests(self):
        """Run multiple requests in parallel."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            client = EnsembleAPIClient(mode=ModelMode.TEST)

            # Mock the complete method
            async def mock_complete(**kwargs):
                return CompletionResult(
                    content=f"Response for: {kwargs.get('messages', [{}])[0].get('content', '')}",
                    input_tokens=50,
                    output_tokens=25,
                    cost=0.0,
                    model_id="test",
                    elapsed_seconds=0.1,
                )

            client.complete = mock_complete

            requests = [
                {"messages": [{"role": "user", "content": f"Request {i}"}]}
                for i in range(5)
            ]

            results = await client.complete_parallel(requests)

            assert len(results) == 5
            for i, result in enumerate(results):
                assert f"Request {i}" in result.content

    @pytest.mark.asyncio
    async def test_parallel_with_semaphore(self):
        """Parallel requests respect max_concurrent limit."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            client = EnsembleAPIClient(mode=ModelMode.TEST)

            call_count = 0
            max_concurrent_seen = 0
            current_concurrent = 0

            async def mock_complete(**kwargs):
                nonlocal call_count, max_concurrent_seen, current_concurrent
                import asyncio

                current_concurrent += 1
                max_concurrent_seen = max(max_concurrent_seen, current_concurrent)
                call_count += 1

                await asyncio.sleep(0.01)  # Small delay

                current_concurrent -= 1
                return CompletionResult(
                    content="Response",
                    input_tokens=10,
                    output_tokens=5,
                    cost=0.0,
                    model_id="test",
                    elapsed_seconds=0.01,
                )

            client.complete = mock_complete

            requests = [{"messages": [{"role": "user", "content": "Test"}]} for _ in range(20)]
            results = await client.complete_parallel(requests, max_concurrent=3)

            assert len(results) == 20
            assert call_count == 20
            assert max_concurrent_seen <= 3  # Semaphore should limit concurrency


class TestGetClient:
    """Tests for get_client convenience function."""

    def test_get_client_test_mode(self):
        """Get client in test mode."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            client = get_client(ModelMode.TEST)
            assert isinstance(client, EnsembleAPIClient)
            assert client.model_config.model_id == "openai/gpt-oss-120b"

    def test_get_client_production_mode(self):
        """Get client in production mode."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = get_client(ModelMode.PRODUCTION)
            assert isinstance(client, EnsembleAPIClient)
            assert client.model_config.model_id == "claude-opus-4-5-20251101"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
