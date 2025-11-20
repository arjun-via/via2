import argparse
import os
from typing import Any, Dict

from alo.agentic_loops.context_loop.agent import ContextLoopAgent
from alo.agentic_loops.core.costs import CostTracker
from alo.agentic_loops.core.logging_utils import TraceRecorder, init_logging
from alo.agentic_loops.core.orchestrator import ALOOrchestrator
from alo.agentic_loops.core.tools import ToolRegistry
from alo.agentic_loops.engineering_loop.agent import EngineeringLoopAgent
from alo.agentic_loops.repro_loop.agent import ReproLoopAgent
from alo.agentic_loops.review_loop.agent import ReviewLoopAgent
from alo.backend.clients.gemini_client import GeminiClient
from alo.backend.clients.openai_client import OpenAICompatibleClient
from alo.config.loader import load_config

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


def build_orchestrator(config: Dict[str, Any], repo_path: str) -> ALOOrchestrator:
    models = config["models"]
    prompts = config.get("prompts", {})
    logger = init_logging(log_path="alo.log", level=config.get("logging", {}).get("level", "INFO"))
    trace_recorder = TraceRecorder("trace.jsonl")
    tool_registry = ToolRegistry(workspace_root=repo_path)
    cost_tracker = CostTracker.get_instance()

    context_client = _safe_client(
        lambda: GeminiClient(
            model=models["context"]["id"],
            api_key=os.getenv("GEMINI_API_KEY", ""),
            # pricing not currently surfaced by SDK responses; tracked elsewhere if available
        ),
        name="context",
    )
    repro_client = _safe_client(
        lambda: OpenAICompatibleClient(
            model=models["repro"]["id"],
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=models["repro"].get("base_url"),
            cost_tracker=cost_tracker,
            prompt_cost_per_1k=_pricing(models["repro"])[0],
            completion_cost_per_1k=_pricing(models["repro"])[1],
        ),
        name="repro",
    )
    engineering_client = _safe_client(
        lambda: OpenAICompatibleClient(
            model=models["engineering"]["id"],
            api_key=os.getenv("CEREBRAS_API_KEY", ""),
            base_url=models["engineering"].get("base_url"),
            cost_tracker=cost_tracker,
            prompt_cost_per_1k=_pricing(models["engineering"])[0],
            completion_cost_per_1k=_pricing(models["engineering"])[1],
        ),
        name="engineering",
    )
    review_client = _safe_client(
        lambda: OpenAICompatibleClient(
            model=models["review"]["id"],
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            base_url=models["review"].get("base_url"),
            cost_tracker=cost_tracker,
            prompt_cost_per_1k=_pricing(models["review"])[0],
            completion_cost_per_1k=_pricing(models["review"])[1],
        ),
        name="review",
    )

    context_agent = ContextLoopAgent(context_client, prompt_template=prompts.get("context"))
    repro_agent = ReproLoopAgent(repro_client, prompt_template=prompts.get("repro"))
    review_agent = ReviewLoopAgent(review_client, prompt_template=prompts.get("review"))
    engineering_agent = EngineeringLoopAgent(
        engineering_client,
        review_agent,
        prompt_template=prompts.get("engineering"),
    )

    return ALOOrchestrator(
        context_agent=context_agent,
        repro_agent=repro_agent,
        engineering_agent=engineering_agent,
        review_agent=review_agent,
        tool_registry=tool_registry,
        logger=logger,
        trace_recorder=trace_recorder,
    )


def _safe_client(factory, name: str):
    try:
        return factory()
    except Exception:
        class StubClient:
            def chat(self, messages, **kwargs):
                return {"content": f"stub response from {name}"}

            def generate(self, prompt, **kwargs):
                return f"stub response from {name}"

        return StubClient()


def _pricing(model_conf: Dict[str, Any]) -> tuple[float, float]:
    pricing = model_conf.get("pricing", {}) if isinstance(model_conf, dict) else {}
    return float(pricing.get("prompt", 0.0)), float(pricing.get("completion", 0.0))


def cli(args: list[str] | None = None) -> None:
    if load_dotenv is not None:
        load_dotenv()

    parser = argparse.ArgumentParser(description="Agentic Loops Orchestrator CLI")
    parser.add_argument("--issue", required=True, help="Issue description to fix")
    parser.add_argument("--repo", required=True, help="Path to target repository")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config YAML (default: config/config.yaml)",
    )

    parsed = parser.parse_args(args)

    config = load_config(parsed.config)
    orchestrator = build_orchestrator(config, repo_path=parsed.repo)
    orchestrator.run(issue_description=parsed.issue, repo_path=parsed.repo)


if __name__ == "__main__":
    cli()
