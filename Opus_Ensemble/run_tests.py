#!/usr/bin/env python
"""
Simple test runner that doesn't depend on pytest.
Uses unittest to run all tests.
"""

import os
import sys
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("OPUS ENSEMBLE TEST SUITE")
    print("=" * 60)
    print()

    # First, verify imports work
    print("Testing imports...")
    try:
        from config import ModelMode, get_config, get_test_config, MODELS
        from data_types import Strategy, PatchCandidate, VerificationResult, EnsembleResult
        from verification import CodeExecutor, Verifier
        from api_client import EnsembleAPIClient, CompletionResult
        from parallel_generator import ParallelGenerator
        from orchestrator import OpusEnsemble
        print("  All imports successful!")
    except Exception as e:
        print(f"  IMPORT ERROR: {e}")
        return 1

    # Test config
    print()
    print("Testing config module...")
    try:
        # Test model modes
        assert ModelMode.PRODUCTION.value == "opus"
        assert ModelMode.TEST.value == "test"
        print("  ModelMode enum: OK")

        # Test MODELS dictionary
        assert ModelMode.PRODUCTION in MODELS
        assert ModelMode.TEST in MODELS
        assert MODELS[ModelMode.PRODUCTION].model_id == "claude-opus-4-5-20251101"
        assert MODELS[ModelMode.TEST].model_id == "openai/gpt-oss-120b"
        print("  MODELS dictionary: OK")

        # Test get_config (with mock env)
        os.environ["OPUS_ENSEMBLE_MODEL"] = "test"
        config = get_config()
        assert config.mode == ModelMode.TEST
        print("  get_config with env var: OK")

        # Test strategy distribution
        config = get_config(ModelMode.PRODUCTION)
        total = sum(config.strategy_distribution.values())
        assert total == 40
        print("  Strategy distribution (40 total): OK")

    except AssertionError as e:
        print(f"  FAILED: {e}")
        return 1
    except Exception as e:
        print(f"  ERROR: {e}")
        return 1

    # Test data types
    print()
    print("Testing data_types module...")
    try:
        # Test Strategy enum
        strategies = list(Strategy)
        assert len(strategies) == 5
        print("  Strategy enum (5 strategies): OK")

        # Test PatchCandidate
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def foo(): pass",
            raw_response="response",
            model_id="test",
        )
        assert patch.instance_id == 0
        assert patch.cost == 0.0  # Default
        print("  PatchCandidate: OK")

        # Test VerificationResult.passed_all
        result = VerificationResult(
            patch=patch,
            syntax_valid=True,
            patch_applies=True,
            reproduction_passes=True,
            regression_passes=True,
        )
        assert result.passed_all is True
        print("  VerificationResult.passed_all: OK")

        # Test pass_rate
        result.tests_passed = 8
        result.tests_total = 10
        assert result.pass_rate == 0.8
        print("  VerificationResult.pass_rate: OK")

    except AssertionError as e:
        print(f"  FAILED: {e}")
        return 1
    except Exception as e:
        print(f"  ERROR: {e}")
        return 1

    # Test verification
    print()
    print("Testing verification module...")
    try:
        # Test CodeExecutor
        executor = CodeExecutor(timeout=10)
        exec_result = executor.execute("print('hello')")
        assert exec_result.success is True
        assert "hello" in exec_result.stdout
        print("  CodeExecutor.execute (valid code): OK")

        exec_result = executor.execute("def broken(")
        assert exec_result.success is False
        print("  CodeExecutor.execute (syntax error): OK")

        # Test Verifier syntax check
        verifier = Verifier(timeout=10)
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def valid(): return 42",
            raw_response="",
            model_id="test",
        )
        result = verifier.verify(patch)
        assert result.syntax_valid is True
        print("  Verifier.verify (valid syntax): OK")

        # Test with failing syntax
        bad_patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def broken(",
            raw_response="",
            model_id="test",
        )
        result = verifier.verify(bad_patch)
        assert result.syntax_valid is False
        assert result.passed_all is False
        print("  Verifier.verify (invalid syntax): OK")

        # Test with passing test
        patch = PatchCandidate(
            instance_id=0,
            strategy=Strategy.MINIMAL,
            code="def add(a, b): return a + b",
            raw_response="",
            model_id="test",
        )
        result = verifier.verify(patch, "assert add(2, 3) == 5")
        assert result.passed_all is True
        print("  Verifier.verify (with passing test): OK")

    except AssertionError as e:
        print(f"  FAILED: {e}")
        return 1
    except Exception as e:
        print(f"  ERROR: {e}")
        return 1

    # Test API client (mock)
    print()
    print("Testing api_client module (mock)...")
    try:
        # Just test initialization doesn't crash
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        client = EnsembleAPIClient(mode=ModelMode.TEST)
        assert client.model_config.model_id == "openai/gpt-oss-120b"
        print("  EnsembleAPIClient init (test mode): OK")

        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        client = EnsembleAPIClient(mode=ModelMode.PRODUCTION)
        assert client.model_config.model_id == "claude-opus-4-5-20251101"
        print("  EnsembleAPIClient init (production mode): OK")

    except AssertionError as e:
        print(f"  FAILED: {e}")
        return 1
    except Exception as e:
        print(f"  ERROR: {e}")
        return 1

    # Test parallel generator (code extraction only, no API calls)
    print()
    print("Testing parallel_generator module...")
    try:
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        generator = ParallelGenerator(mode=ModelMode.TEST)

        # Test code extraction
        response = '```python\ndef fix(): return 42\n```'
        code = generator._extract_code(response)
        assert code == "def fix(): return 42"
        print("  ParallelGenerator._extract_code (python block): OK")

        response = '```diff\n--- a/file.py\n+++ b/file.py\n```'
        code = generator._extract_code(response)
        assert "---" in code
        print("  ParallelGenerator._extract_code (diff block): OK")

        response = "inline code only"
        code = generator._extract_code(response)
        assert code == "inline code only"
        print("  ParallelGenerator._extract_code (no block): OK")

    except AssertionError as e:
        print(f"  FAILED: {e}")
        return 1
    except Exception as e:
        print(f"  ERROR: {e}")
        return 1

    # Test orchestrator init
    print()
    print("Testing orchestrator module...")
    try:
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        ensemble = OpusEnsemble(mode=ModelMode.TEST)
        assert ensemble.config.mode == ModelMode.TEST
        print("  OpusEnsemble init: OK")

    except AssertionError as e:
        print(f"  FAILED: {e}")
        return 1
    except Exception as e:
        print(f"  ERROR: {e}")
        return 1

    print()
    print("=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(run_tests())
