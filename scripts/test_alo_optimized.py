"""Test ALO-Optimized runner."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.runners.alo_optimized_runner import ALOOptimizedRunner

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    print("\nTesting ALO-Optimized...")
    print("="*60)
    print("Config:")
    print("  Context: Gemini 2.5 Flash (massive context)")
    print("  Engineering: Qwen3-Coder 480B (specialized, 20x cheaper)")
    print("  Review: Kimi-K2-Thinking (deep reasoning)")
    print("="*60)

    runner = ALOOptimizedRunner()

    # Rate limiter test (same as ALO vs ALO-Open comparison)
    prompt = "Implement a rate limiter using the token bucket algorithm in Python. Include thread safety and support for multiple users."

    print(f"\nRunning on: Rate Limiter (Token Bucket)")
    result = runner.run(prompt)

    print(f"\n✓ ALO-Optimized test complete!")
    print(f"Cost: ${result.cost:.4f}")
    print(f"Time: {result.elapsed_time:.2f}s")
    print(f"Output length: {len(result.output)} chars")
    print(f"\nFirst 300 chars:")
    print(result.output[:300])


if __name__ == "__main__":
    main()
