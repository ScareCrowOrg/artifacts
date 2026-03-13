"""
Unit tests for rate limiting utilities.

Tests cover:
- Rate limiter initialization
- Batch processing with delays
- Concurrency control
- Statistics tracking
- Error handling
"""

import pytest
import time
from unittest.mock import Mock, patch
from threading import Thread
import sys

# Import the rate limiter module
from app.utils.rate_limiter import RateLimiter, create_embedding_rate_limiter


class TestRateLimiter:
    """Test suite for RateLimiter class."""
    
    def test_initialization_default_values(self):
        """Test rate limiter initialization with default values."""
        limiter = RateLimiter()
        
        assert limiter.batch_size == 10
        assert limiter.batch_delay == 0.5
        assert limiter.max_concurrent == 1
        
    def test_initialization_custom_values(self):
        """Test rate limiter initialization with custom values."""
        limiter = RateLimiter(
            batch_size=20,
            batch_delay=1.0,
            max_concurrent=3
        )
        
        assert limiter.batch_size == 20
        assert limiter.batch_delay == 1.0
        assert limiter.max_concurrent == 3
    
    def test_process_in_batches_empty_list(self):
        """Test processing empty list returns empty results."""
        limiter = RateLimiter(batch_size=5)
        
        def process_func(batch):
            return len(batch)
        
        results = limiter.process_in_batches([], process_func)
        
        assert results == []
    
    def test_process_in_batches_single_batch(self):
        """Test processing items that fit in a single batch."""
        limiter = RateLimiter(batch_size=10, batch_delay=0.1)
        items = list(range(5))
        
        def process_func(batch):
            return sum(batch)
        
        results = limiter.process_in_batches(items, process_func)
        
        assert len(results) == 1
        assert results[0] == sum(items)
    
    def test_process_in_batches_multiple_batches(self):
        """Test processing items split across multiple batches."""
        limiter = RateLimiter(batch_size=3, batch_delay=0.05)
        items = list(range(10))  # Will create 4 batches: [0,1,2], [3,4,5], [6,7,8], [9]
        
        processed_batches = []
        
        def process_func(batch):
            processed_batches.append(batch)
            return len(batch)
        
        results = limiter.process_in_batches(items, process_func)
        
        assert len(results) == 4
        assert results == [3, 3, 3, 1]
        assert len(processed_batches) == 4
    
    def test_process_in_batches_with_delay(self):
        """Test that delays are applied between batches."""
        limiter = RateLimiter(batch_size=2, batch_delay=0.2)
        items = list(range(6))  # 3 batches
        
        start_time = time.time()
        
        def process_func(batch):
            return batch
        
        limiter.process_in_batches(items, process_func)
        
        elapsed = time.time() - start_time
        
        # Should have 2 delays (between 3 batches)
        # Allow some tolerance for execution time
        assert elapsed >= 0.4  # 2 * 0.2s
        assert elapsed < 1.0  # Should not be too slow
    
    def test_process_in_batches_with_progress_callback(self):
        """Test that progress callback is called correctly."""
        limiter = RateLimiter(batch_size=2, batch_delay=0.05)
        items = list(range(5))  # 3 batches
        
        progress_calls = []
        
        def progress_callback(current, total):
            progress_calls.append((current, total))
        
        def process_func(batch):
            return batch
        
        limiter.process_in_batches(
            items,
            process_func,
            progress_callback=progress_callback
        )
        
        assert len(progress_calls) == 3
        assert progress_calls[0] == (1, 3)
        assert progress_calls[1] == (2, 3)
        assert progress_calls[2] == (3, 3)
    
    def test_process_in_batches_error_handling(self):
        """Test that errors in processing are propagated."""
        limiter = RateLimiter(batch_size=2, batch_delay=0.05)
        items = list(range(5))
        
        def process_func(batch):
            if len(batch) == 2:
                raise ValueError("Test error")
            return batch
        
        with pytest.raises(ValueError, match="Test error"):
            limiter.process_in_batches(items, process_func)
    
    def test_acquire_context_manager(self):
        """Test acquire context manager for concurrency control."""
        limiter = RateLimiter(max_concurrent=2)
        
        # Should be able to acquire twice
        with limiter.acquire():
            assert limiter._active_operations == 1
            with limiter.acquire():
                assert limiter._active_operations == 2
        
        # Should release after exiting context
        assert limiter._active_operations == 0
    
    def test_acquire_blocks_when_at_limit(self):
        """Test that acquire blocks when max concurrent is reached."""
        limiter = RateLimiter(max_concurrent=1)
        
        def worker():
            with limiter.acquire():
                time.sleep(0.2)
        
        start_time = time.time()
        
        # Start two threads that should run sequentially
        t1 = Thread(target=worker)
        t2 = Thread(target=worker)
        
        t1.start()
        time.sleep(0.05)  # Ensure t1 acquires first
        t2.start()
        
        t1.join()
        t2.join()
        
        elapsed = time.time() - start_time
        
        # Should take at least 0.4s (two sequential operations of 0.2s each)
        assert elapsed >= 0.4
    
    def test_get_stats(self):
        """Test statistics tracking."""
        limiter = RateLimiter(batch_size=3, batch_delay=0.05)
        items = list(range(10))
        
        def process_func(batch):
            return batch
        
        limiter.process_in_batches(items, process_func)
        
        stats = limiter.get_stats()
        
        assert stats['total_requests'] == 10
        assert stats['total_batches'] == 4
        assert stats['batch_size'] == 3
        assert stats['batch_delay'] == 0.05
        assert stats['max_concurrent'] == 1
        assert stats['active_operations'] == 0
    
    def test_reset_stats(self):
        """Test resetting statistics."""
        limiter = RateLimiter(batch_size=2)
        items = list(range(5))
        
        def process_func(batch):
            return batch
        
        limiter.process_in_batches(items, process_func)
        
        stats_before = limiter.get_stats()
        assert stats_before['total_requests'] > 0
        
        limiter.reset_stats()
        
        stats_after = limiter.get_stats()
        assert stats_after['total_requests'] == 0
        assert stats_after['total_batches'] == 0
    
    def test_zero_batch_delay(self):
        """Test that zero batch delay is handled correctly."""
        limiter = RateLimiter(batch_size=2, batch_delay=0)
        items = list(range(6))
        
        start_time = time.time()
        
        def process_func(batch):
            return batch
        
        limiter.process_in_batches(items, process_func)
        
        elapsed = time.time() - start_time
        
        # Should be fast with no delays
        assert elapsed < 0.5


class TestCreateEmbeddingRateLimiter:
    """Test suite for create_embedding_rate_limiter factory function."""
    
    def test_create_with_defaults_from_config(self):
        """Test creating rate limiter with config defaults."""
        with patch('app.config.EMBEDDING_BATCH_SIZE', 15):
            with patch('app.config.EMBEDDING_BATCH_DELAY', 0.8):
                with patch('app.config.EMBEDDING_MAX_CONCURRENT', 2):
                    limiter = create_embedding_rate_limiter()
                    
                    assert limiter.batch_size == 15
                    assert limiter.batch_delay == 0.8
                    assert limiter.max_concurrent == 2
    
    def test_create_with_overrides(self):
        """Test creating rate limiter with parameter overrides."""
        limiter = create_embedding_rate_limiter(
            batch_size=25,
            batch_delay=1.5,
            max_concurrent=3
        )
        
        assert limiter.batch_size == 25
        assert limiter.batch_delay == 1.5
        assert limiter.max_concurrent == 3
    
    def test_create_with_partial_overrides(self):
        """Test creating rate limiter with some parameter overrides."""
        with patch('app.config.EMBEDDING_BATCH_SIZE', 10):
            with patch('app.config.EMBEDDING_BATCH_DELAY', 0.5):
                with patch('app.config.EMBEDDING_MAX_CONCURRENT', 1):
                    limiter = create_embedding_rate_limiter(
                        batch_size=20  # Override only batch_size
                    )
                    
                    assert limiter.batch_size == 20  # Overridden
                    assert limiter.batch_delay == 0.5  # From config
                    assert limiter.max_concurrent == 1  # From config


class TestRateLimiterIntegration:
    """Integration tests for rate limiter with realistic scenarios."""
    
    def test_realistic_embedding_scenario(self):
        """Test rate limiter with a realistic embedding generation scenario."""
        limiter = RateLimiter(batch_size=5, batch_delay=0.1, max_concurrent=1)
        
        # Simulate 25 chunks to embed
        chunks = [f"chunk_{i}" for i in range(25)]
        
        processed_chunks = []
        batch_times = []
        
        def process_batch(batch):
            """Simulate embedding generation with some processing time."""
            start = time.time()
            time.sleep(0.05)  # Simulate API call
            processed_chunks.extend(batch)
            batch_times.append(time.time() - start)
            return len(batch)
        
        results = limiter.process_in_batches(chunks, process_batch)
        
        # Verify all chunks were processed
        assert len(processed_chunks) == 25
        assert len(results) == 5  # 25 chunks / 5 per batch
        
        # Verify batches were processed
        assert sum(results) == 25
        
        # Verify delays were applied (4 delays between 5 batches)
        stats = limiter.get_stats()
        assert stats['total_batches'] == 5
    
    def test_concurrent_rate_limiter_access(self):
        """Test that rate limiter handles concurrent access correctly."""
        limiter = RateLimiter(batch_size=2, batch_delay=0.05, max_concurrent=2)
        
        results = []
        
        def worker(items):
            def process_func(batch):
                return batch
            
            result = limiter.process_in_batches(items, process_func)
            results.append(result)
        
        # Create two threads processing different items
        items1 = list(range(5))
        items2 = list(range(5, 10))
        
        t1 = Thread(target=worker, args=(items1,))
        t2 = Thread(target=worker, args=(items2,))
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # Both threads should complete successfully
        assert len(results) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
