"""
ALO v2.0 - Opus-Orchestrated Agentic Loop

ARCHITECTURE:
- Opus (claude-opus-4-5-20251101): Orchestrator brain
- Kimi K2 (via OpenRouter): Default worker
- Gemini 3 Flash (via OpenRouter): Large context worker

API KEYS REQUIRED:
- ANTHROPIC_API_KEY: For Opus orchestrator
- OPENROUTER_API_KEY: For workers (Kimi K2, Gemini 3 Flash)
"""

from .orchestrator import ALOv2Orchestrator
from .config import Config, ModelConfig
from .clients import ClientFactory, ModelResponse, AnthropicClient, OpenRouterClient
from .docker_executor import DockerExecutor, ExecutionResult
from .worker_dispatch import WorkerDispatcher, WorkerType, WorkerSelection

__version__ = "2.0.0"
__all__ = [
    "ALOv2Orchestrator",
    "Config",
    "ModelConfig",
    "ClientFactory",
    "ModelResponse",
    "AnthropicClient",
    "OpenRouterClient",
    "DockerExecutor",
    "ExecutionResult",
    "WorkerDispatcher",
    "WorkerType",
    "WorkerSelection",
]
