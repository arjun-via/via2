"""Test each model in ALO-Open configuration via OpenRouter."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


MODELS_TO_TEST = {
    "Kimi-K2 (review)": {"id": "moonshotai/kimi-k2-0905", "provider": "Groq"},
    "Kimi-K2-Thinking (context)": {"id": "moonshotai/kimi-k2-thinking", "provider": "Groq"},
    "GLM-4.6 (repro)": {"id": "z-ai/glm-4.6", "provider": "Cerebras"},
    "Qwen3-Coder 480B (engineering)": {"id": "qwen/qwen3-coder", "provider": None},
}

TEST_PROMPT = "Write a Python function to calculate fibonacci numbers. Just respond with 'OK' if you can see this."


def test_model(model_config: dict, model_name: str) -> bool:
    """Test a single model via OpenRouter."""
    model_id = model_config["id"]
    provider = model_config.get("provider")

    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print(f"Model ID: {model_id}")
    if provider:
        print(f"Provider: {provider}")
    print(f"{'='*60}")

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY", "")
        )

        kwargs = {
            "model": model_id,
            "messages": [{"role": "user", "content": TEST_PROMPT}],
            "max_tokens": 100,
            "temperature": 0
        }

        # Add provider specification if needed
        if provider:
            kwargs["extra_body"] = {
                "provider": {
                    "order": [provider]
                }
            }

        response = client.chat.completions.create(**kwargs)

        output = response.choices[0].message.content
        print(f"✓ SUCCESS")
        print(f"Response: {output[:100]}...")
        print(f"Tokens: {response.usage.prompt_tokens} prompt, {response.usage.completion_tokens} completion")
        return True

    except Exception as e:
        print(f"✗ FAILED")
        print(f"Error: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("ALO-Open Model Testing via OpenRouter")
    print("="*60)

    if not os.getenv("OPENROUTER_API_KEY"):
        print("\n⚠️  WARNING: OPENROUTER_API_KEY not found in environment")
        return

    results = {}
    for name, model_config in MODELS_TO_TEST.items():
        results[name] = test_model(model_config, name)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    for name, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status:8} {name}")

    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} models working")

    if passed == total:
        print("\n✓ All models working! ALO-Open is ready to use.")
    else:
        print(f"\n⚠️  {total - passed} model(s) failed. Check errors above.")


if __name__ == "__main__":
    main()
