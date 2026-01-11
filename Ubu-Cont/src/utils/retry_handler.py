"""
Retry Handler - Provides retry logic with exponential backoff.

This module provides decorators and utilities for retrying
failed operations with configurable backoff strategies.
"""

import asyncio
import functools
from typing import Callable, TypeVar, Any, Optional, Type, Tuple
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class RetryError(Exception):
    """Raised when all retry attempts have failed."""
    
    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


async def retry_async(
    func: Callable[..., T],
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
) -> T:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to call
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts in seconds
        backoff: Multiplier for delay after each attempt
        max_delay: Maximum delay between attempts
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback when a retry occurs
        
    Returns:
        Result of the function
        
    Raises:
        RetryError: If all attempts fail
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            
            if attempt == max_attempts:
                logger.error(f"All {max_attempts} attempts failed")
                raise RetryError(
                    f"Failed after {max_attempts} attempts: {str(e)}",
                    last_exception
                )
            
            logger.warning(
                f"Attempt {attempt}/{max_attempts} failed: {str(e)}. "
                f"Retrying in {current_delay:.1f}s..."
            )
            
            if on_retry:
                on_retry(attempt, e)
            
            await asyncio.sleep(current_delay)
            current_delay = min(current_delay * backoff, max_delay)
    
    raise RetryError("Unexpected error in retry logic", last_exception)


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for retrying async functions.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff: Multiplier for delay after each attempt
        max_delay: Maximum delay between attempts
        exceptions: Tuple of exceptions to catch and retry
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            async def call():
                return await func(*args, **kwargs)
            
            return await retry_async(
                call,
                max_attempts=max_attempts,
                delay=delay,
                backoff=backoff,
                max_delay=max_delay,
                exceptions=exceptions
            )
        return wrapper
    return decorator


class RetryContext:
    """
    Context manager for tracking retry state.
    
    Usage:
        retry_ctx = RetryContext(max_attempts=3)
        while retry_ctx.should_retry():
            try:
                result = await do_something()
                retry_ctx.success()
                break
            except Exception as e:
                await retry_ctx.handle_error(e)
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        max_delay: float = 30.0
    ):
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff = backoff
        self.max_delay = max_delay
        
        self.current_attempt = 0
        self.current_delay = delay
        self.succeeded = False
        self.last_exception: Optional[Exception] = None
        self.start_time = datetime.now()
    
    def should_retry(self) -> bool:
        """Check if we should attempt another retry."""
        if self.succeeded:
            return False
        return self.current_attempt < self.max_attempts
    
    async def handle_error(self, exception: Exception) -> bool:
        """
        Handle an error and wait before retry.
        
        Args:
            exception: The exception that occurred
            
        Returns:
            True if we will retry, False if out of attempts
        """
        self.last_exception = exception
        self.current_attempt += 1
        
        if self.current_attempt >= self.max_attempts:
            logger.error(f"All {self.max_attempts} attempts exhausted")
            return False
        
        logger.warning(
            f"Attempt {self.current_attempt}/{self.max_attempts} failed: {str(exception)}. "
            f"Retrying in {self.current_delay:.1f}s..."
        )
        
        await asyncio.sleep(self.current_delay)
        self.current_delay = min(self.current_delay * self.backoff, self.max_delay)
        
        return True
    
    def success(self):
        """Mark the operation as successful."""
        self.succeeded = True
        self.current_attempt += 1
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds since context creation."""
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_attempts(self) -> int:
        """Get the number of attempts made."""
        return self.current_attempt
    
    def raise_if_failed(self):
        """Raise RetryError if all attempts failed."""
        if not self.succeeded and self.last_exception:
            raise RetryError(
                f"Failed after {self.current_attempt} attempts",
                self.last_exception
            )


async def with_timeout(
    func: Callable[..., T],
    timeout: float,
    *args,
    **kwargs
) -> T:
    """
    Execute a function with a timeout.
    
    Args:
        func: Async function to call
        timeout: Timeout in seconds
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Result of the function
        
    Raises:
        asyncio.TimeoutError: If timeout exceeded
    """
    return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
