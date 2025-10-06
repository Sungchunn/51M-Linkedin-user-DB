"""
INSIGHT - Retry Logic with Exponential Backoff
Handles API failures gracefully with retry logic

Negative Spaces Implementation:
- Max retries enforced (prevents infinite loops)
- Exponential backoff capped at 60s
- Logs all retry attempts with context
"""

import time
import logging
from typing import Callable, TypeVar, Optional
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Sentinel for failure
RETRY_FAILED = object()


def exponential_backoff(retry_count: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """
    Calculate exponential backoff delay.

    NEGATIVE SPACE CONTRACT:
    - retry_count must be >= 0
    - Delay grows exponentially: 1s, 2s, 4s, 8s, 16s, 32s, 60s (capped)
    - Returns delay in seconds

    Args:
        retry_count: Number of retries attempted (0-indexed)
        base_delay: Base delay in seconds (default 1.0)
        max_delay: Maximum delay cap in seconds (default 60.0)

    Returns:
        Delay in seconds
    """
    if retry_count < 0:
        raise ValueError(f"NEGATIVE SPACE: retry_count must be >= 0, got {retry_count}")

    # Calculate exponential delay: base_delay * 2^retry_count
    delay = base_delay * (2 ** retry_count)

    # Cap at max_delay
    delay = min(delay, max_delay)

    return delay


def sleep_with_backoff(retry_count: int, base_delay: float = 1.0, max_delay: float = 60.0):
    """
    Sleep with exponential backoff.

    NEGATIVE SPACE CONTRACT:
    - Blocks for calculated delay time
    - Logs delay duration

    Args:
        retry_count: Number of retries attempted
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
    """
    delay = exponential_backoff(retry_count, base_delay, max_delay)

    logger.info(f"Retry {retry_count + 1}: Backing off for {delay:.1f}s")
    time.sleep(delay)


def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
) -> Optional[T]:
    """
    Retry a function with exponential backoff.

    NEGATIVE SPACE CONTRACT:
    - max_retries must be > 0
    - Returns result on success
    - Returns None after max_retries exhausted
    - Logs all attempts and failures

    Args:
        func: Function to retry (no arguments)
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Function result or None if all retries failed
    """
    if max_retries <= 0:
        raise ValueError(f"NEGATIVE SPACE: max_retries must be > 0, got {max_retries}")

    for attempt in range(max_retries):
        try:
            result = func()

            if attempt > 0:
                logger.info(f"✅ Retry succeeded on attempt {attempt + 1}")

            return result

        except exceptions as e:
            if attempt < max_retries - 1:
                # Not the last attempt - retry
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {e.__class__.__name__}: {e}"
                )
                sleep_with_backoff(attempt, base_delay, max_delay)
            else:
                # Last attempt - give up
                logger.error(
                    f"❌ All {max_retries} retry attempts failed. Last error: {e}",
                    exc_info=True
                )
                return None

    # Should never reach here, but for type safety
    return None


def retry_decorator(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for automatic retry with exponential backoff.

    NEGATIVE SPACE CONTRACT:
    - Wraps function to add retry logic
    - Preserves function signature
    - Returns None on failure

    Example:
        @retry_decorator(max_retries=3, exceptions=(OpenAIError, Timeout))
        def generate_embedding(text: str) -> list:
            return openai.embed(text)

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Optional[T]:
            def _func():
                return func(*args, **kwargs)

            return retry_with_backoff(
                _func,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                exceptions=exceptions
            )

        return wrapper

    return decorator


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted"""
    pass


def retry_with_exception(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,),
    context: str = ""
) -> T:
    """
    Retry a function with exponential backoff, raise exception on failure.

    NEGATIVE SPACE CONTRACT:
    - Returns result on success
    - Raises RetryExhaustedError after max_retries
    - Never returns None (use retry_with_backoff for that)

    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        exceptions: Tuple of exceptions to catch and retry
        context: Context string for error messages

    Returns:
        Function result

    Raises:
        RetryExhaustedError: If all retries fail
    """
    result = retry_with_backoff(func, max_retries, base_delay, max_delay, exceptions)

    if result is None:
        raise RetryExhaustedError(
            f"NEGATIVE SPACE: Retry exhausted after {max_retries} attempts. "
            f"Context: {context}"
        )

    return result
