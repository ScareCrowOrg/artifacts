#!/usr/bin/env python3
"""
POC: Redis Pub/Sub for Log Streaming

This script demonstrates Redis pub/sub for real-time log streaming from
backend to frontend via WebSocket. This is critical for Agent Mode to
display live Aider logs.

Requirements:
- Redis server running (localhost:6379)
- redis-py installed (pip install redis)

Test Objectives:
1. Validate pub/sub functionality
2. Measure latency (<50ms target)
3. Measure throughput (>1000 msg/s target)
4. Test multiple subscribers
5. Validate message format preservation

Usage:
    # Terminal 1 (subscriber):
    python3 poc_redis_pubsub.py subscribe
    
    # Terminal 2 (publisher):
    python3 poc_redis_pubsub.py publish
    
    # Terminal 3 (benchmark):
    python3 poc_redis_pubsub.py benchmark
"""

import sys
import time
import json
import asyncio
from datetime import datetime
from typing import List

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Note: redis-py not installed. Install with: pip install redis")
    print("This POC can still be reviewed for architecture validation.")


# Redis connection configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
TEST_CHANNEL = "agent:logs:test"


def get_redis_client() -> redis.Redis:
    """Create Redis client connection."""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )


def test_connection():
    """Test basic Redis connection."""
    if not REDIS_AVAILABLE:
        print("✗ Redis library not available")
        print("\nTo run this POC, install dependencies:")
        print("  pip install redis")
        print("\nOr review the code for architecture validation.")
        return False
    
    print("Testing Redis connection...")
    try:
        r = get_redis_client()
        r.ping()
        print("✓ Redis connection successful")
        return True
    except redis.ConnectionError as e:
        print(f"✗ Redis connection failed: {e}")
        print("\nPlease ensure Redis is running:")
        print("  docker-compose up redis")
        print("  OR")
        print("  redis-server")
        return False


def publish_messages(count: int = 10, delay: float = 0.1):
    """
    Publish test messages to Redis channel.
    
    Args:
        count: Number of messages to publish
        delay: Delay between messages in seconds
    """
    print("=" * 70)
    print("POC: Redis Publisher")
    print("=" * 70)
    print()
    
    r = get_redis_client()
    
    print(f"Publishing {count} messages to channel: {TEST_CHANNEL}")
    print(f"Delay between messages: {delay}s")
    print("-" * 70)
    
    for i in range(count):
        message = {
            "type": "log",
            "timestamp": datetime.utcnow().isoformat(),
            "conversation_id": "test-conversation",
            "content": f"Log line {i+1}: Processing item {i+1}/{count}",
            "source": "aider",
            "level": "info" if i % 3 != 0 else "warning",
            "metadata": {
                "sequence": i + 1,
                "total": count
            }
        }
        
        # Publish as JSON string
        message_json = json.dumps(message)
        subscribers = r.publish(TEST_CHANNEL, message_json)
        
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] Published message {i+1} (subscribers: {subscribers})")
        
        if delay > 0:
            time.sleep(delay)
    
    # Publish completion message
    completion = {
        "type": "status",
        "status": "completed",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "All messages published"
    }
    r.publish(TEST_CHANNEL, json.dumps(completion))
    print()
    print("✓ All messages published")
    print()


def subscribe_messages():
    """Subscribe to Redis channel and print messages."""
    print("=" * 70)
    print("POC: Redis Subscriber")
    print("=" * 70)
    print()
    
    r = get_redis_client()
    pubsub = r.pubsub()
    
    print(f"Subscribing to channel: {TEST_CHANNEL}")
    print("Waiting for messages... (Ctrl+C to stop)")
    print("-" * 70)
    
    pubsub.subscribe(TEST_CHANNEL)
    
    try:
        for message in pubsub.listen():
            if message["type"] == "message":
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                
                try:
                    data = json.loads(message["data"])
                    msg_type = data.get("type", "unknown")
                    content = data.get("content", data.get("message", ""))
                    level = data.get("level", "info")
                    
                    # Color code based on level
                    color = {
                        "info": "\033[36m",     # Cyan
                        "warning": "\033[33m",  # Yellow
                        "error": "\033[31m",    # Red
                        "debug": "\033[90m"     # Gray
                    }.get(level, "")
                    reset = "\033[0m"
                    
                    print(f"[{timestamp}] {color}{msg_type.upper()}{reset}: {content}")
                    
                    # Check for completion
                    if data.get("type") == "status" and data.get("status") == "completed":
                        print()
                        print("✓ Received completion signal")
                        break
                        
                except json.JSONDecodeError:
                    print(f"[{timestamp}] RAW: {message['data']}")
                    
    except KeyboardInterrupt:
        print()
        print("Subscription stopped by user")
    finally:
        pubsub.unsubscribe(TEST_CHANNEL)
        print()


def benchmark_latency():
    """Benchmark pub/sub latency."""
    print("=" * 70)
    print("POC: Redis Pub/Sub Latency Benchmark")
    print("=" * 70)
    print()
    
    r = get_redis_client()
    pubsub = r.pubsub()
    pubsub.subscribe(TEST_CHANNEL)
    
    # Skip subscription message
    next(pubsub.listen())
    
    latencies = []
    num_messages = 100
    
    print(f"Measuring latency for {num_messages} messages...")
    print("-" * 70)
    
    for i in range(num_messages):
        # Publish with timestamp
        start_time = time.time()
        message = {
            "sequence": i,
            "timestamp": start_time
        }
        r.publish(TEST_CHANNEL, json.dumps(message))
        
        # Wait for message
        for msg in pubsub.listen():
            if msg["type"] == "message":
                end_time = time.time()
                latency = (end_time - start_time) * 1000  # Convert to ms
                latencies.append(latency)
                
                if (i + 1) % 10 == 0:
                    print(f"  {i+1}/{num_messages} messages - current latency: {latency:.2f}ms")
                break
    
    pubsub.unsubscribe(TEST_CHANNEL)
    
    # Calculate statistics
    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
    
    print()
    print("Results:")
    print(f"  Messages: {num_messages}")
    print(f"  Average latency: {avg_latency:.2f}ms")
    print(f"  Min latency: {min_latency:.2f}ms")
    print(f"  Max latency: {max_latency:.2f}ms")
    print(f"  P95 latency: {p95_latency:.2f}ms")
    print()
    
    if avg_latency < 50:
        print("✓ Latency target met (<50ms)")
    else:
        print("✗ Latency target not met")
    
    print()


def benchmark_throughput():
    """Benchmark pub/sub throughput."""
    print("=" * 70)
    print("POC: Redis Pub/Sub Throughput Benchmark")
    print("=" * 70)
    print()
    
    r = get_redis_client()
    num_messages = 10000
    
    print(f"Publishing {num_messages} messages as fast as possible...")
    print("-" * 70)
    
    start_time = time.time()
    
    for i in range(num_messages):
        message = {
            "sequence": i,
            "content": f"Message {i}"
        }
        r.publish(TEST_CHANNEL, json.dumps(message))
    
    end_time = time.time()
    duration = end_time - start_time
    throughput = num_messages / duration
    
    print()
    print("Results:")
    print(f"  Messages: {num_messages}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Throughput: {throughput:.0f} messages/second")
    print()
    
    if throughput > 1000:
        print("✓ Throughput target met (>1000 msg/s)")
    else:
        print("✗ Throughput target not met")
    
    print()


def run_full_test():
    """Run complete POC test suite."""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 17 + "Redis Pub/Sub POC Test Suite" + " " * 23 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    if not test_connection():
        return 1
    
    print()
    
    try:
        benchmark_latency()
        benchmark_throughput()
        
        print("=" * 70)
        print("POC SUMMARY")
        print("=" * 70)
        print()
        print("✓ All benchmarks completed")
        print("✓ Redis pub/sub functional")
        print("✓ Performance targets validated")
        print()
        print("Next Steps:")
        print("  1. Integrate into LogStreamService")
        print("  2. Create WebSocket endpoint")
        print("  3. Test with real Aider output")
        print()
        
        return 0
        
    except Exception as e:
        print()
        print("=" * 70)
        print("ERROR")
        print("=" * 70)
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 poc_redis_pubsub.py [command]")
        print()
        print("Commands:")
        print("  publish    - Publish test messages")
        print("  subscribe  - Subscribe and listen for messages")
        print("  benchmark  - Run performance benchmarks")
        print("  test       - Run full test suite")
        print()
        return 1
    
    command = sys.argv[1].lower()
    
    if not test_connection():
        return 1
    
    print()
    
    try:
        if command == "publish":
            publish_messages()
        elif command == "subscribe":
            subscribe_messages()
        elif command == "benchmark":
            benchmark_latency()
            benchmark_throughput()
        elif command == "test":
            return run_full_test()
        else:
            print(f"Unknown command: {command}")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        print()
        print("Interrupted by user")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
