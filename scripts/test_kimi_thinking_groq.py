"""Test if Kimi-K2-Thinking is available via Groq provider on OpenRouter."""
import os
from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def test_kimi_thinking_with_groq():
    """Test Kimi-K2-Thinking with Groq provider."""
    print("Testing: moonshotai/kimi-k2-thinking with Groq provider via OpenRouter")
    print("=" * 80)

    client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1"
    )

    test_prompt = "Write a simple Python function to check if a number is prime. Include docstring."

    try:
        print("\nSending test request...")
        response = client.chat.completions.create(
            model="moonshotai/kimi-k2-thinking",
            messages=[
                {"role": "user", "content": test_prompt}
            ],
            extra_body={
                "provider": {
                    "order": ["Groq"]
                }
            },
            max_tokens=500
        )

        print("✓ SUCCESS!")
        print(f"\nModel used: {response.model}")
        print(f"Response length: {len(response.choices[0].message.content)} chars")
        print(f"\nResponse preview:")
        print("-" * 80)
        print(response.choices[0].message.content[:500])
        print("-" * 80)

        # Check usage
        if hasattr(response, 'usage'):
            print(f"\nTokens: {response.usage.prompt_tokens} prompt + {response.usage.completion_tokens} completion")

        return True

    except Exception as e:
        print(f"✗ FAILED!")
        print(f"Error: {e}")
        print("\nThis likely means Groq does NOT support Kimi-K2-Thinking")
        return False


def test_without_provider():
    """Test Kimi-K2-Thinking without specifying provider."""
    print("\n" + "=" * 80)
    print("Testing: moonshotai/kimi-k2-thinking WITHOUT provider specification")
    print("=" * 80)

    client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1"
    )

    test_prompt = "Write a simple Python function to check if a number is prime. Include docstring."

    try:
        print("\nSending test request (default provider)...")
        response = client.chat.completions.create(
            model="moonshotai/kimi-k2-thinking",
            messages=[
                {"role": "user", "content": test_prompt}
            ],
            max_tokens=500
        )

        print("✓ SUCCESS!")
        print(f"\nModel used: {response.model}")
        print(f"Response length: {len(response.choices[0].message.content)} chars")

        return True

    except Exception as e:
        print(f"✗ FAILED!")
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    print("KIMI-K2-THINKING PROVIDER TEST")
    print("=" * 80)

    # Test with Groq
    groq_works = test_kimi_thinking_with_groq()

    # Test without provider
    default_works = test_without_provider()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Kimi-K2-Thinking with Groq provider: {'✓ WORKS' if groq_works else '✗ DOES NOT WORK'}")
    print(f"Kimi-K2-Thinking default provider: {'✓ WORKS' if default_works else '✗ DOES NOT WORK'}")

    if not groq_works and default_works:
        print("\n⚠️  RECOMMENDATION: Use Kimi-K2-Thinking WITHOUT provider specification")
        print("    (OpenRouter will route to the default provider)")
