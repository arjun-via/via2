"""Test script for CodeEvaluator."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.evaluators import CodeEvaluator, CodeEvalResult


def test_syntax_validation():
    """Test syntax validation."""
    evaluator = CodeEvaluator()

    # Valid code
    valid_code = """
```python
def hello():
    print("Hello, World!")
```
"""
    result = evaluator.evaluate(valid_code)
    assert result.syntax_valid, "Valid code should pass syntax check"

    # Invalid code
    invalid_code = """
```python
def hello(
    print("Missing closing paren")
```
"""
    result = evaluator.evaluate(invalid_code)
    assert not result.syntax_valid, "Invalid code should fail syntax check"
    assert "SyntaxError" in result.syntax_error

    print("✓ Syntax validation tests passed")


def test_execution():
    """Test code execution."""
    evaluator = CodeEvaluator()

    # Code that executes successfully
    good_code = """
```python
x = 1 + 1
print(f"Result: {x}")
```
"""
    result = evaluator.evaluate(good_code)
    assert result.executes, "Simple code should execute"

    # Code with import error
    bad_import = """
```python
import nonexistent_module
```
"""
    result = evaluator.evaluate(bad_import)
    assert not result.executes, "Code with bad import should not execute"
    assert result.error_type == "ImportError"

    print("✓ Execution tests passed")


def test_pattern_matching():
    """Test pattern matching for specific prompts."""
    evaluator = CodeEvaluator()

    # Rate limiter with required patterns
    rate_limiter_code = """
```python
import threading
import time

class RateLimiter:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_request = time.time()
```
"""
    result = evaluator.evaluate(rate_limiter_code, "rate_limiter")
    assert result.has_required_patterns, "Rate limiter should have required patterns"
    assert len(result.found_patterns) == 2

    # Rate limiter missing threading
    bad_rate_limiter = """
```python
import time

class RateLimiter:
    def __init__(self):
        self.last_request = time.time()
```
"""
    result = evaluator.evaluate(bad_rate_limiter, "rate_limiter")
    assert not result.has_required_patterns, "Should detect missing patterns"
    assert len(result.missing_patterns) > 0

    print("✓ Pattern matching tests passed")


def test_full_evaluation():
    """Test complete evaluation pipeline."""
    evaluator = CodeEvaluator()

    code = """
```python
import threading
import time
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
            return None

    def put(self, key, value):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
```
"""
    result = evaluator.evaluate(code, "lru_cache")

    print("\nFull Evaluation Results:")
    print(f"  Syntax Valid: {result.syntax_valid}")
    print(f"  Executes: {result.executes}")
    print(f"  Has Required Patterns: {result.has_required_patterns}")
    print(f"  Found Patterns: {result.found_patterns}")
    print(f"  Missing Patterns: {result.missing_patterns}")

    assert result.syntax_valid, "Should be syntactically valid"
    assert result.executes, "Should execute without errors"
    assert result.has_required_patterns, "Should have LRU cache patterns"

    print("\n✓ Full evaluation test passed")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing CodeEvaluator")
    print("=" * 60)

    test_syntax_validation()
    test_execution()
    test_pattern_matching()
    test_full_evaluation()

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
