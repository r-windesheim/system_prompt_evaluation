"""
Simple Rate Limiter for API calls
Prevents overwhelming OpenRouter with too many requests
"""

import asyncio
import time
from typing import Optional


class RateLimiter:
    """
    Token bucket rate limiter for API calls
    """

    def __init__(self, max_per_second: int = 10, burst_size: Optional[int] = None):
        """
        Initialize rate limiter

        Args:
            max_per_second: Maximum requests per second
            burst_size: Maximum burst size (defaults to max_per_second)
        """
        self.max_per_second = max_per_second
        self.burst_size = burst_size or max_per_second
        self.tokens = float(self.burst_size)
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens, waiting if necessary

        Args:
            tokens: Number of tokens to acquire
        """
        async with self.lock:
            while tokens > self.tokens:
                # Calculate how many tokens we've accumulated
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(
                    self.burst_size,
                    self.tokens + elapsed * self.max_per_second
                )
                self.last_update = now

                if tokens > self.tokens:
                    # Not enough tokens, wait for them to accumulate
                    needed = tokens - self.tokens
                    wait_time = needed / self.max_per_second
                    await asyncio.sleep(wait_time)

            # Consume tokens
            self.tokens -= tokens

    async def __aenter__(self):
        """Context manager entry"""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        pass


# Global rate limiter for OpenRouter
# Conservative: 5 requests per second to avoid rate limits
openrouter_limiter = RateLimiter(max_per_second=5, burst_size=10)