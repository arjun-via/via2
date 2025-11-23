import argparse
import os
import sys
from typing import Any, Dict

from alo.agentic_loops.context_loop.agent import ContextLoopAgent
from alo.agentic_loops.core.costs import CostTracker
from alo.agentic_loops.core.logging_utils import TraceRecorder, init_logging
from alo.agentic_loops.core.orchestrator import ALOOrchestrator
from alo.agentic_loops.core.prompt_orchestrator import PromptOrchestrator
from alo.agentic_loops.core.tools import ToolRegistry
from alo.agentic_loops.engineering_loop.agent import EngineeringLoopAgent
from alo.agentic_loops.prompt_loop.agent import PromptLoopAgent
from alo.agentic_loops.repro_loop.agent import ReproLoopAgent
from alo.agentic_loops.review_loop.agent import ReviewLoopAgent
from alo.backend.clients.gemini_client import GeminiClient
from alo.backend.clients.openai_client import OpenAICompatibleClient
from alo.config.loader import load_config

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def build_orchestrator(config: Dict[str, Any], repo_path: str) -> ALOOrchestrator:
    models = config["models"]
    prompts = config.get("prompts", {})
    logger = init_logging(log_path="alo.log", level=config.get("logging", {}).get("level", "INFO"))
    trace_recorder = TraceRecorder("trace.jsonl")
    tool_registry = ToolRegistry(workspace_root=repo_path)
    cost_tracker = CostTracker.get_instance()

    def _context_client():
        return _context_client_from_config(models["context"])

    context_client = _safe_client(_context_client, name="context")
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
            api_key=_get_api_key_for_url(models["engineering"].get("base_url", "")),
            base_url=models["engineering"].get("base_url"),
            extra_body=_build_extra_body(models["engineering"]),
            cost_tracker=cost_tracker,
            prompt_cost_per_1k=_pricing(models["engineering"])[0],
            completion_cost_per_1k=_pricing(models["engineering"])[1],
        ),
        name="engineering",
    )
    review_client = _safe_client(
        lambda: OpenAICompatibleClient(
            model=models["review"]["id"],
            api_key=_get_api_key_for_url(models["review"].get("base_url", "")),
            base_url=models["review"].get("base_url"),
            extra_body=_build_extra_body(models["review"]),
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


def build_prompt_orchestrator(config: Dict[str, Any]) -> PromptOrchestrator:
    models = config["models"]
    prompts = config.get("prompts", {})
    logger = init_logging(log_path="alo.log", level=config.get("logging", {}).get("level", "INFO"))
    trace_recorder = TraceRecorder("trace.jsonl")
    cost_tracker = CostTracker.get_instance()

    context_client = _safe_client(
        lambda: _context_client_from_config(models["context"]),
        name="context",
    )
    review_client = _safe_client(
        lambda: OpenAICompatibleClient(
            model=models["review"]["id"],
            api_key=_get_api_key_for_url(models["review"].get("base_url", "")),
            base_url=models["review"].get("base_url"),
            extra_body=_build_extra_body(models["review"]),
            cost_tracker=cost_tracker,
            prompt_cost_per_1k=_pricing(models["review"])[0],
            completion_cost_per_1k=_pricing(models["review"])[1],
        ),
        name="review",
    )
    prompt_client = _safe_client(
        lambda: OpenAICompatibleClient(
            model=models["engineering"]["id"],
            api_key=_get_api_key_for_url(models["engineering"].get("base_url", "")),
            base_url=models["engineering"].get("base_url"),
            extra_body=_build_extra_body(models["engineering"]),
            cost_tracker=cost_tracker,
            prompt_cost_per_1k=_pricing(models["engineering"])[0],
            completion_cost_per_1k=_pricing(models["engineering"])[1],
        ),
        name="prompt",
    )

    context_agent = ContextLoopAgent(context_client, prompt_template=prompts.get("context"))
    review_agent = ReviewLoopAgent(review_client, prompt_template=prompts.get("review"))
    prompt_agent = PromptLoopAgent(
        prompt_client,
        review_agent,
        prompt_template=prompts.get("engineering"),
    )
    return PromptOrchestrator(
        context_agent=context_agent,
        prompt_agent=prompt_agent,
        logger=logger,
        trace_recorder=trace_recorder,
        cost_tracker=cost_tracker,
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


def _get_api_key_for_url(base_url: str) -> str:
    """Select the right API key based on the base_url."""
    if not base_url:
        return ""
    if "anthropic.com" in base_url:
        return os.getenv("ANTHROPIC_API_KEY", "")
    if "openrouter.ai" in base_url:
        return os.getenv("OPENROUTER_API_KEY", "")
    if "cerebras.ai" in base_url:
        return os.getenv("CEREBRAS_API_KEY", "")
    # Default to OPENAI_API_KEY for openai.com and others
    return os.getenv("OPENAI_API_KEY", "")


def _build_extra_body(model_conf: Dict[str, Any]) -> Dict[str, Any]:
    """Build extra_body dict with provider specification if present."""
    extra_body = {}
    provider = model_conf.get("provider")
    if provider:
        extra_body["provider"] = {"order": [provider]}
    return extra_body


def _context_client_from_config(ctx_conf: Dict[str, Any]):
    base_url = ctx_conf.get("base_url")
    if base_url:
        cost_tracker = CostTracker.get_instance()
        return OpenAICompatibleClient(
            model=ctx_conf["id"],
            api_key=_get_api_key_for_url(base_url),
            base_url=base_url,
            extra_body=_build_extra_body(ctx_conf),
            cost_tracker=cost_tracker,
            prompt_cost_per_1k=_pricing(ctx_conf)[0],
            completion_cost_per_1k=_pricing(ctx_conf)[1],
        )
    return GeminiClient(
        model=ctx_conf["id"],
        api_key=os.getenv("GEMINI_API_KEY", ""),
    )


def cli(args: list[str] | None = None) -> None:
    if load_dotenv is not None:
        load_dotenv()

    parser = argparse.ArgumentParser(description="Agentic Loops Orchestrator CLI")
    parser.add_argument("--issue", help="Issue description to fix (code mode)")
    parser.add_argument("--repo", help="Path to target repository (code mode)")
    parser.add_argument("--prompt", help="General prompt to answer (prompt mode)")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config YAML (default: config/config.yaml)",
    )

    parsed = parser.parse_args(args)
    config = load_config(parsed.config)

    if parsed.prompt:
        prompt_orch = build_prompt_orchestrator(config)
        cost_tracker = CostTracker.get_instance()
        cost_tracker.reset()
        state, elapsed, cost_summary = prompt_orch.run(parsed.prompt)
        print(state.final_answer.strip())
        print("\n---")
        print(f"Elapsed: {elapsed:.2f}s | Estimated cost: ${cost_summary.get('total_cost', 0.0):.4f}")
        if cost_summary.get("by_model"):
            for model, stats in cost_summary["by_model"].items():
                print(
                    f"  {model}: prompts={stats.get('prompt_tokens',0)} "
                    f"completions={stats.get('completion_tokens',0)} "
                    f"cost=${stats.get('cost',0.0):.4f}"
                )
    else:
        if not parsed.issue or not parsed.repo:
            parser.error("--issue and --repo are required unless --prompt is provided")
        orchestrator = build_orchestrator(config, repo_path=parsed.repo)
        orchestrator.run(issue_description=parsed.issue, repo_path=parsed.repo)


if __name__ == "__main__":
    sys.exit(cli())
