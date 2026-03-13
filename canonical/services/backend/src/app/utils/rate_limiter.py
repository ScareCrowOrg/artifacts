"""
Rate Limiting Utilities for Ollama Embeddings

This module provides rate limiting and throttling mechanisms to prevent
overwhelming the Ollama backend service with too many concurrent requests.

Key features:
- Batch processing of embedding requests
- Configurable delays between batches
- Concurrency control
- Request counting and monitoring
"""

import logging
import time
from contextlib import contextmanager
from threading import Lock
from typing import Any, Callable, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RateLimiter:
    """
    Rate limiter for controlling request frequency to external services.

    This class implements batch processing with concurrency control and
    configurable delays between batches to prevent overwhelming external services.
    """

    def __init__(
        self, batch_size: int = 10, batch_delay: float = 0.5, max_concurrent: int = 1
    ):
        """
        Initialize rate limiter.

        Args:
            batch_size: Number of items to process per batch
            batch_delay: Delay in seconds between batches
            max_concurrent: Maximum concurrent operations allowed
        """
        self.batch_size = batch_size
        self.batch_delay = batch_delay
        self.max_concurrent = max_concurrent
        self._lock = Lock()
        self._active_operations = 0
        self._total_requests = 0
        self._total_batches = 0

    @contextmanager
    def acquire(self):
        """
        Context manager to acquire a slot for operation.

        Blocks until a slot is available within the max_concurrent limit.
        Uses exponential backoff to reduce busy-waiting overhead.
        """
        # Wait until we have capacity with exponential backoff
        wait_time = 0.01  # Start with 10ms
        max_wait = 0.5  # Cap at 500ms

        while True:
            with self._lock:
                if self._active_operations < self.max_concurrent:
                    self._active_operations += 1
                    break

            # Exponential backoff with cap
            time.sleep(wait_time)
            wait_time = min(wait_time * 2, max_wait)

        try:
            yield
        finally:
            with self._lock:
                self._active_operations -= 1

    def process_in_batches(
        self,
        items: List[T],
        process_func: Callable[[List[T]], Any],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Any]:
        """
        Process items in rate-limited batches.

        Args:
            items: List of items to process
            process_func: Function to process each batch
            progress_callback: Optional callback(current_batch, total_batches)

        Returns:
            List of results from all batches
        """
        if not items:
            return []

        # Split into batches
        batches = [
            items[i : i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]

        total_batches = len(batches)
        logger.info(
            "Processing %s items in %s batches (batch_size=%s, delay=%ss)",
            len(items), total_batches, self.batch_size, self.batch_delay
        )

        results = []

        for batch_idx, batch in enumerate(batches, 1):
            with self.acquire():
                logger.debug("Processing batch %s/%s (%s items)", batch_idx, total_batches, len(batch))

                start_time = time.time()

                try:
                    batch_result = process_func(batch)
                    results.append(batch_result)

                    with self._lock:
                        self._total_requests += len(batch)
                        self._total_batches += 1

                    elapsed = time.time() - start_time
                    logger.debug("Batch %s/%s completed in %ss", batch_idx, total_batches, elapsed)

                except Exception as e:
                    logger.error("Error processing batch %s/%s: %s", batch_idx, total_batches, e)
                    raise

                # Call progress callback if provided
                if progress_callback:
                    progress_callback(batch_idx, total_batches)

                # Add delay between batches (except after last batch)
                if batch_idx < total_batches and self.batch_delay > 0:
                    logger.debug("Waiting %ss before next batch", self.batch_delay)
                    time.sleep(self.batch_delay)

        logger.info("Completed processing %s items in %s batches", len(items), total_batches)

        return results

    def get_stats(self) -> dict:
        """
        Get rate limiter statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            return {
                "total_requests": self._total_requests,
                "total_batches": self._total_batches,
                "active_operations": self._active_operations,
                "batch_size": self.batch_size,
                "batch_delay": self.batch_delay,
                "max_concurrent": self.max_concurrent,
            }

    def reset_stats(self):
        """Reset statistics counters."""
        with self._lock:
            self._total_requests = 0
            self._total_batches = 0


def create_embedding_rate_limiter(
    batch_size: Optional[int] = None,
    batch_delay: Optional[float] = None,
    max_concurrent: Optional[int] = None,
) -> RateLimiter:
    """
    Create a rate limiter configured for embedding generation.

    Uses values from config if not provided.

    Args:
        batch_size: Override default batch size
        batch_delay: Override default batch delay
        max_concurrent: Override default max concurrent

    Returns:
        Configured RateLimiter instance
    """
    from app.config import (
        EMBEDDING_BATCH_DELAY,
        EMBEDDING_BATCH_SIZE,
        EMBEDDING_MAX_CONCURRENT,
    )

    return RateLimiter(
        batch_size=batch_size or EMBEDDING_BATCH_SIZE,
        batch_delay=batch_delay or EMBEDDING_BATCH_DELAY,
        max_concurrent=max_concurrent or EMBEDDING_MAX_CONCURRENT,
    )
