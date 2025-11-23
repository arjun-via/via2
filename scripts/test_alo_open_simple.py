"""Simple test of ALO-Open runner."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.runners.alo_open_runner import ALOOpenRunner

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    print("\nTesting ALO-Open with simple prompt...")
    print("="*60)

    runner = ALOOpenRunner()
    result = runner.run("Write a Python function to reverse a string.")

    print(f"\n✓ ALO-Open test successful!")
    print(f"Output length: {len(result.output)} chars")
    print(f"Cost: ${result.cost:.4f}")
    print(f"Time: {result.elapsed_time:.2f}s")
    print(f"\nFirst 200 chars of output:")
    print(result.output[:200])


if __name__ == "__main__":
    main()
