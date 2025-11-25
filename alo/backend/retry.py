"""
=============================================================================
SCRIPT NAME: retry.py
=============================================================================

Retry logic with exponential backoff for API calls.

This module provides robust retry handling for transient API failures:
- Rate limiting (429 errors)
- Timeout errors
- Connection errors
- Server errors (5xx)

The retry decorator uses exponential backoff with jitter to avoid
thundering herd problems when multiple clients retry simultaneously.

VERSION: 1.0
LAST UPDATED: 2025-01-24
=============================================================================
"""

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Tuple, Type

logger = logging.getLogger(__name__)


# Default configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 60.0  # seconds
DEFAULT_EXPONENTIAL_BASE = 2
DEFAULT_JITTER = 0.1  # 10% jitter


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, original_error: Exception, attempts: int):
        self.original_error = original_error
        self.attempts = attempts
        message = (
            f"All {attempts} retry attempts exhausted. "
            f"Last error: {type(original_error).__name__}: {original_error}"
        )
        super().__init__(message)


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is transient and worth retrying.

    Returns True for:
    - Rate limit errors (429)
    - Timeout errors
    - Connection errors
    - Server errors (5xx)

    Returns False for:
    - Authentication errors (401, 403)
    - Bad request errors (400)
    - Not found errors (404)
    - Other client errors
    """
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    # Check for rate limiting
    if "rate" in error_str and "limit" in error_str:
        return True
    if "429" in error_str or "too many requests" in error_str:
        return True

    # Check for timeout
    if "timeout" in error_str or "timeout" in error_type:
        return True
    if "timed out" in error_str:
        return True

    # Check for connection errors
    if "connection" in error_type or "connection" in error_str:
        return True
    if "network" in error_str:
        return True

    # Check for server errors (5xx)
    if "500" in error_str or "502" in error_str or "503" in error_str or "504" in error_str:
        return True
    if "server error" in error_str or "internal error" in error_str:
        return True
    if "service unavailable" in error_str:
        return True

    # Check for OpenAI-specific retryable errors
    if "apierror" in error_type:
        # APIError from openai package - check status code
        if hasattr(error, "status_code"):
            status = getattr(error, "status_code", 0)
            return status >= 500 or status == 429

    # Check for Google API errors
    if "resourceexhausted" in error_type or "resourceexhausted" in error_str:
        return True

    # Default: don't retry unknown errors
    return False


def calculate_delay(
    attempt: int,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
    jitter: float = DEFAULT_JITTER,
) -> float:
    """Calculate delay for next retry with exponential backoff and jitter.

    Formula: min(max_delay, initial_delay * (base ^ attempt)) * (1 + random_jitter)
    """
    delay = min(max_delay, initial_delay * (exponential_base ** attempt))
    # Add jitter to avoid thundering herd
    jitter_amount = delay * jitter * random.random()
    return delay + jitter_amount


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
    jitter: float = DEFAULT_JITTER,
    retryable_exceptions: Tuple[Type[Exception], ...] | None = None,
    on_retry: Callable[[Exception, int, float], None] | None = None,
) -> Callable:
    """Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2)
        jitter: Jitter factor (0.0-1.0) to randomize delays (default: 0.1)
        retryable_exceptions: Tuple of exception types to retry (default: all transient)
        on_retry: Optional callback(error, attempt, delay) called before each retry

    Returns:
        Decorated function that retries on transient failures

    Example:
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_api():
            return api.chat(...)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    # Check if this error is retryable
                    should_retry = False
                    if retryable_exceptions:
                        should_retry = isinstance(e, retryable_exceptions)
                    else:
                        should_retry = is_retryable_error(e)

                    if not should_retry:
                        # Not a retryable error, fail immediately
                        raise

                    if attempt >= max_retries:
                        # No more retries left
                        raise RetryExhaustedError(e, attempt + 1) from e

                    # Calculate delay for next retry
                    delay = calculate_delay(
                        attempt,
                        initial_delay=initial_delay,
                        max_delay=max_delay,
                        exponential_base=exponential_base,
                        jitter=jitter,
                    )

                    # Log the retry
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {type(e).__name__}: {e}. "
                        f"Waiting {delay:.2f}s before retry..."
                    )

                    # Call optional callback
                    if on_retry:
                        on_retry(e, attempt + 1, delay)

                    # Wait before retry
                    time.sleep(delay)

            # Should never reach here, but just in case
            if last_error:
                raise RetryExhaustedError(last_error, max_retries + 1)
            raise RuntimeError("Unexpected state in retry loop")

        return wrapper
    return decorator


class RetryConfig:
    """Configuration class for retry behavior.

    Can be passed to clients to customize retry behavior.
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_delay: float = DEFAULT_INITIAL_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
        exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
        jitter: float = DEFAULT_JITTER,
        enabled: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.enabled = enabled

    @classmethod
    def disabled(cls) -> "RetryConfig":
        """Create a config with retries disabled."""
        return cls(enabled=False, max_retries=0)

    @classmethod
    def aggressive(cls) -> "RetryConfig":
        """Create a config with aggressive retry settings."""
        return cls(max_retries=5, initial_delay=0.5, max_delay=30.0)

    @classmethod
    def conservative(cls) -> "RetryConfig":
        """Create a config with conservative retry settings."""
        return cls(max_retries=2, initial_delay=2.0, max_delay=120.0)
