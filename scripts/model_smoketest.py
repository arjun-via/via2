import argparse
import os
import sys

from alo.backend.clients.gemini_client import GeminiClient
from alo.backend.clients.openai_client import OpenAICompatibleClient
from alo.config.loader import load_config

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test configured models.")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config YAML (default: config/config.yaml)",
    )
    args = parser.parse_args()

    if load_dotenv:
        load_dotenv()

    config = load_config(args.config)
    models = config["models"]
    results = []

    # Context / Gemini
    try:
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        ctx_client = GeminiClient(model=models["context"]["id"], api_key=gemini_key)
        resp = ctx_client.generate(prompt="ping")
        results.append(("context/gemini", True, str(resp)[:200]))
    except Exception as exc:
        results.append(("context/gemini", False, str(exc)))

    # Orchestrator (Anthropic)
    try:
        orch_conf = models["orchestrator"]
        client = OpenAICompatibleClient(
            model=orch_conf["id"],
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            base_url=orch_conf.get("base_url"),
        )
        resp = client.chat([{"role": "user", "content": "ping"}])
        results.append(("orchestrator/anthropic", True, str(resp["content"])[:200]))
    except Exception as exc:
        results.append(("orchestrator/anthropic", False, str(exc)))

    # Repro / Engineering / Review with OpenAI-compatible
    for name, env_var in (("repro", "OPENAI_API_KEY"), ("engineering", "CEREBRAS_API_KEY"), ("review", "OPENROUTER_API_KEY")):
        model_conf = models[name]
        try:
            client = OpenAICompatibleClient(
                model=model_conf["id"],
                api_key=os.getenv(env_var, ""),
                base_url=model_conf.get("base_url"),
            )
            resp = client.chat([{"role": "user", "content": "ping"}])
            results.append((f"{name}/{model_conf.get('base_url','')}", True, str(resp["content"])[:200]))
        except Exception as exc:
            results.append((f"{name}/{model_conf.get('base_url','')}", False, str(exc)))

    for name, ok, info in results:
        status = "OK" if ok else "FAIL"
        print(f"{name}: {status} - {info}")

    failed = [r for r in results if not r[1]]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
