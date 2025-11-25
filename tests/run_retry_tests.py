#!/usr/bin/env python
"""
Direct test runner for API Retry with Backoff tests.

Demonstrates:
- BEFORE: Single attempt, immediate failure on transient errors
- AFTER: Automatic retry with exponential backoff
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch


def print_test(name, passed, details=""):
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {name}")
    if details and not passed:
        print(f"         {details}")


def run_tests():
    print("\n" + "=" * 70)
    print("API RETRY WITH BACKOFF - Test Results")
    print("=" * 70)

    passed = 0
    failed = 0

    from alo.backend.retry import (
        RetryConfig,
        RetryExhaustedError,
        retry_with_backoff,
        is_retryable_error,
        calculate_delay,
    )

    # =========================================================================
    # TEST GROUP 1: Error Classification
    # =========================================================================
    print("\n--- Group 1: Error Classification ---")

    # Test 1.1: Rate limit errors are retryable
    try:
        rate_limit_errors = [
            Exception("Rate limit exceeded"),
            Exception("429 Too Many Requests"),
            Exception("rate limit reached for model"),
        ]
        all_retryable = all(is_retryable_error(e) for e in rate_limit_errors)
        if all_retryable:
            print_test("Rate limit errors are retryable", True)
            passed += 1
        else:
            print_test("Rate limit errors are retryable", False)
            failed += 1
    except Exception as e:
        print_test("Rate limit errors are retryable", False, str(e))
        failed += 1

    # Test 1.2: Timeout errors are retryable
    try:
        timeout_errors = [
            TimeoutError("Connection timed out"),
            Exception("Request timeout"),
            Exception("timed out waiting for response"),
        ]
        all_retryable = all(is_retryable_error(e) for e in timeout_errors)
        if all_retryable:
            print_test("Timeout errors are retryable", True)
            passed += 1
        else:
            print_test("Timeout errors are retryable", False)
            failed += 1
    except Exception as e:
        print_test("Timeout errors are retryable", False, str(e))
        failed += 1

    # Test 1.3: Server errors (5xx) are retryable
    try:
        server_errors = [
            Exception("500 Internal Server Error"),
            Exception("502 Bad Gateway"),
            Exception("503 Service Unavailable"),
            Exception("504 Gateway Timeout"),
        ]
        all_retryable = all(is_retryable_error(e) for e in server_errors)
        if all_retryable:
            print_test("Server errors (5xx) are retryable", True)
            passed += 1
        else:
            print_test("Server errors (5xx) are retryable", False)
            failed += 1
    except Exception as e:
        print_test("Server errors (5xx) are retryable", False, str(e))
        failed += 1

    # Test 1.4: Connection errors are retryable
    try:
        conn_errors = [
            ConnectionError("Connection refused"),
            Exception("Network unreachable"),
        ]
        all_retryable = all(is_retryable_error(e) for e in conn_errors)
        if all_retryable:
            print_test("Connection errors are retryable", True)
            passed += 1
        else:
            print_test("Connection errors are retryable", False)
            failed += 1
    except Exception as e:
        print_test("Connection errors are retryable", False, str(e))
        failed += 1

    # Test 1.5: Auth/client errors are NOT retryable
    try:
        non_retryable_errors = [
            Exception("401 Unauthorized"),
            Exception("403 Forbidden"),
            ValueError("Invalid parameter"),
            KeyError("missing_key"),
        ]
        none_retryable = not any(is_retryable_error(e) for e in non_retryable_errors)
        if none_retryable:
            print_test("Auth/client errors are NOT retryable", True)
            passed += 1
        else:
            print_test("Auth/client errors are NOT retryable", False)
            failed += 1
    except Exception as e:
        print_test("Auth/client errors are NOT retryable", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 2: Exponential Backoff Calculation
    # =========================================================================
    print("\n--- Group 2: Exponential Backoff ---")

    # Test 2.1: Delay increases exponentially
    try:
        delays = [calculate_delay(i, initial_delay=1.0, jitter=0) for i in range(4)]
        # Expected: 1, 2, 4, 8 (with base 2)
        expected = [1.0, 2.0, 4.0, 8.0]
        # Allow small floating point differences
        matches = all(abs(d - e) < 0.01 for d, e in zip(delays, expected))
        if matches:
            print_test("Delay increases exponentially", True)
            passed += 1
        else:
            print_test("Delay increases exponentially", False, f"Got {delays}")
            failed += 1
    except Exception as e:
        print_test("Delay increases exponentially", False, str(e))
        failed += 1

    # Test 2.2: Delay capped at max_delay
    try:
        delay = calculate_delay(10, initial_delay=1.0, max_delay=30.0, jitter=0)
        # 2^10 = 1024, but should be capped at 30
        if delay == 30.0:
            print_test("Delay capped at max_delay", True)
            passed += 1
        else:
            print_test("Delay capped at max_delay", False, f"Got {delay}")
            failed += 1
    except Exception as e:
        print_test("Delay capped at max_delay", False, str(e))
        failed += 1

    # Test 2.3: Jitter adds randomness
    try:
        # With jitter=0.1, delays should vary slightly
        delays = [calculate_delay(1, initial_delay=1.0, jitter=0.1) for _ in range(10)]
        # All delays should be close to 2.0 (base delay) but not identical
        all_close = all(1.9 < d < 2.3 for d in delays)
        has_variance = len(set(delays)) > 1  # Not all the same
        if all_close and has_variance:
            print_test("Jitter adds randomness to delays", True)
            passed += 1
        else:
            print_test("Jitter adds randomness to delays", False,
                       f"all_close={all_close}, has_variance={has_variance}")
            failed += 1
    except Exception as e:
        print_test("Jitter adds randomness to delays", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 3: Retry Decorator Behavior
    # =========================================================================
    print("\n--- Group 3: Retry Decorator ---")

    # Test 3.1: Successful call on first attempt (no retry needed)
    try:
        call_count = [0]

        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        def success_first_try():
            call_count[0] += 1
            return "success"

        result = success_first_try()
        if result == "success" and call_count[0] == 1:
            print_test("No retry when first attempt succeeds", True)
            passed += 1
        else:
            print_test("No retry when first attempt succeeds", False,
                       f"calls={call_count[0]}")
            failed += 1
    except Exception as e:
        print_test("No retry when first attempt succeeds", False, str(e))
        failed += 1

    # Test 3.2: Retry on transient error, succeed on retry
    try:
        call_count = [0]

        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        def fail_then_succeed():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("503 Service Unavailable")
            return "success"

        result = fail_then_succeed()
        if result == "success" and call_count[0] == 3:
            print_test("Retry on transient error, succeed on 3rd attempt", True)
            passed += 1
        else:
            print_test("Retry on transient error, succeed on 3rd attempt", False,
                       f"calls={call_count[0]}")
            failed += 1
    except Exception as e:
        print_test("Retry on transient error, succeed on 3rd attempt", False, str(e))
        failed += 1

    # Test 3.3: No retry on non-transient error
    try:
        call_count = [0]

        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        def auth_error():
            call_count[0] += 1
            raise ValueError("Invalid API key")

        try:
            auth_error()
            print_test("No retry on non-transient error", False, "No exception raised")
            failed += 1
        except ValueError:
            if call_count[0] == 1:
                print_test("No retry on non-transient error", True)
                passed += 1
            else:
                print_test("No retry on non-transient error", False,
                           f"calls={call_count[0]}")
                failed += 1
    except Exception as e:
        print_test("No retry on non-transient error", False, str(e))
        failed += 1

    # Test 3.4: RetryExhaustedError after max retries
    try:
        call_count = [0]

        @retry_with_backoff(max_retries=2, initial_delay=0.01)
        def always_fail():
            call_count[0] += 1
            raise Exception("429 Rate limit exceeded")

        try:
            always_fail()
            print_test("RetryExhaustedError after max retries", False, "No exception raised")
            failed += 1
        except RetryExhaustedError as e:
            # Should have tried 3 times (initial + 2 retries)
            if call_count[0] == 3 and e.attempts == 3:
                print_test("RetryExhaustedError after max retries", True)
                passed += 1
            else:
                print_test("RetryExhaustedError after max retries", False,
                           f"calls={call_count[0]}, attempts={e.attempts}")
                failed += 1
    except Exception as e:
        print_test("RetryExhaustedError after max retries", False, str(e))
        failed += 1

    # Test 3.5: on_retry callback is called
    try:
        retry_info = []

        def on_retry_callback(error, attempt, delay):
            retry_info.append({"attempt": attempt, "delay": delay})

        call_count = [0]

        @retry_with_backoff(max_retries=2, initial_delay=0.01, on_retry=on_retry_callback)
        def fail_twice():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("500 Server Error")
            return "success"

        fail_twice()

        if len(retry_info) == 2:
            print_test("on_retry callback is called for each retry", True)
            passed += 1
        else:
            print_test("on_retry callback is called for each retry", False,
                       f"callback calls={len(retry_info)}")
            failed += 1
    except Exception as e:
        print_test("on_retry callback is called for each retry", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 4: RetryConfig
    # =========================================================================
    print("\n--- Group 4: RetryConfig ---")

    # Test 4.1: Default config
    try:
        config = RetryConfig()
        if config.max_retries == 3 and config.enabled:
            print_test("Default RetryConfig has 3 retries enabled", True)
            passed += 1
        else:
            print_test("Default RetryConfig has 3 retries enabled", False)
            failed += 1
    except Exception as e:
        print_test("Default RetryConfig has 3 retries enabled", False, str(e))
        failed += 1

    # Test 4.2: Disabled config
    try:
        config = RetryConfig.disabled()
        if config.max_retries == 0 and not config.enabled:
            print_test("RetryConfig.disabled() disables retries", True)
            passed += 1
        else:
            print_test("RetryConfig.disabled() disables retries", False)
            failed += 1
    except Exception as e:
        print_test("RetryConfig.disabled() disables retries", False, str(e))
        failed += 1

    # Test 4.3: Aggressive config
    try:
        config = RetryConfig.aggressive()
        if config.max_retries == 5 and config.initial_delay == 0.5:
            print_test("RetryConfig.aggressive() has more retries", True)
            passed += 1
        else:
            print_test("RetryConfig.aggressive() has more retries", False)
            failed += 1
    except Exception as e:
        print_test("RetryConfig.aggressive() has more retries", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 5: Client Integration
    # =========================================================================
    print("\n--- Group 5: Client Integration ---")

    # Test 5.1: OpenAICompatibleClient uses retry
    try:
        from alo.backend.clients.openai_client import OpenAICompatibleClient

        call_count = [0]
        mock_client = MagicMock()

        def mock_create(**kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("429 Rate limit exceeded")
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="test"))]
            mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
            return mock_response

        mock_client.chat.completions.create = mock_create

        client = OpenAICompatibleClient(
            model="test",
            client=mock_client,
            retry_config=RetryConfig(max_retries=3, initial_delay=0.01),
        )

        result = client.chat([{"role": "user", "content": "test"}])

        if call_count[0] == 2 and result["content"] == "test":
            print_test("OpenAICompatibleClient retries on rate limit", True)
            passed += 1
        else:
            print_test("OpenAICompatibleClient retries on rate limit", False,
                       f"calls={call_count[0]}")
            failed += 1
    except Exception as e:
        print_test("OpenAICompatibleClient retries on rate limit", False, str(e))
        import traceback
        traceback.print_exc()
        failed += 1

    # Test 5.2: Client with retry disabled doesn't retry
    try:
        from alo.backend.clients.openai_client import OpenAICompatibleClient

        call_count = [0]
        mock_client = MagicMock()

        def mock_create_fail(**kwargs):
            call_count[0] += 1
            raise Exception("429 Rate limit exceeded")

        mock_client.chat.completions.create = mock_create_fail

        client = OpenAICompatibleClient(
            model="test",
            client=mock_client,
            retry_config=RetryConfig.disabled(),
        )

        try:
            client.chat([{"role": "user", "content": "test"}])
            print_test("Client with disabled retry doesn't retry", False, "No exception")
            failed += 1
        except Exception:
            if call_count[0] == 1:
                print_test("Client with disabled retry doesn't retry", True)
                passed += 1
            else:
                print_test("Client with disabled retry doesn't retry", False,
                           f"calls={call_count[0]}")
                failed += 1
    except Exception as e:
        print_test("Client with disabled retry doesn't retry", False, str(e))
        failed += 1

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    total = passed + failed
    print(f"SUMMARY: {passed}/{total} tests passed")

    if failed > 0:
        print(f"\n❌ {failed} test(s) FAILED")
        return 1
    else:
        print(f"\n✅ All {passed} tests PASSED - API Retry with Backoff working!")
        return 0


if __name__ == "__main__":
    sys.exit(run_tests())
