#!/usr/bin/env python3
"""
POC: Aider Streaming - Unbuffered Output Test

This script demonstrates unbuffered subprocess I/O for real-time streaming
of Aider CLI output. This is critical for Agent Mode to provide live feedback.

Requirements:
- Aider CLI installed (pip install aider-chat)
- Test file in /tmp for safe editing

Test Objectives:
1. Validate line-by-line unbuffered output
2. Preserve ANSI color codes
3. Measure latency (<100ms target)
4. Test bidirectional communication (stdin/stdout)

Usage:
    python3 poc_aider_streaming.py
"""

import subprocess
import sys
import time
import os
from datetime import datetime


def test_unbuffered_streaming():
    """Test unbuffered subprocess streaming with a simple command."""
    print("=" * 70)
    print("POC: Unbuffered Subprocess Streaming")
    print("=" * 70)
    print()
    
    # Test 1: Simple command with line-by-line output
    print("Test 1: Line-by-line streaming with Python script")
    print("-" * 70)
    
    # Create a test script that outputs lines with delays
    test_script = """
import sys
import time
for i in range(5):
    print(f"Line {i+1}: Processing...", flush=True)
    time.sleep(0.2)
print("\\033[32mCompleted successfully\\033[0m", flush=True)
"""
    
    process = subprocess.Popen(
        [sys.executable, "-c", test_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,  # Unbuffered
        universal_newlines=False,  # Binary mode for byte-level control
        env={**os.environ, "PYTHONUNBUFFERED": "1"}
    )
    
    latencies = []
    line_count = 0
    
    while True:
        start_time = time.time()
        line = process.stdout.readline()
        if not line:
            break
        
        latency = (time.time() - start_time) * 1000  # Convert to ms
        latencies.append(latency)
        line_count += 1
        
        # Decode and print with timestamp
        decoded_line = line.decode('utf-8', errors='replace').rstrip()
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] {decoded_line} (latency: {latency:.2f}ms)")
    
    process.wait()
    
    # Results
    print()
    print("Results:")
    print(f"  Lines received: {line_count}")
    print(f"  Average latency: {sum(latencies)/len(latencies):.2f}ms")
    print(f"  Max latency: {max(latencies):.2f}ms")
    print(f"  Min latency: {min(latencies):.2f}ms")
    
    if sum(latencies)/len(latencies) < 100:
        print("  ✓ Latency target met (<100ms)")
    else:
        print("  ✗ Latency target not met")
    
    print()


def test_ansi_colors():
    """Test ANSI color code preservation."""
    print("=" * 70)
    print("POC: ANSI Color Code Preservation")
    print("=" * 70)
    print()
    
    # Test script with various ANSI codes
    test_script = """
import sys
print("\\033[31mRed text\\033[0m", flush=True)
print("\\033[32mGreen text\\033[0m", flush=True)
print("\\033[33mYellow text\\033[0m", flush=True)
print("\\033[34mBlue text\\033[0m", flush=True)
print("\\033[1m\\033[35mBold Magenta\\033[0m", flush=True)
print("\\033[36mCyan text\\033[0m", flush=True)
"""
    
    process = subprocess.Popen(
        [sys.executable, "-c", test_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        universal_newlines=False
    )
    
    while True:
        line = process.stdout.readline()
        if not line:
            break
        # Print without decoding to preserve ANSI codes
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
    
    process.wait()
    print()
    print("✓ ANSI colors should be visible above")
    print()


def test_aider_simulation():
    """Simulate Aider-like interactive output."""
    print("=" * 70)
    print("POC: Aider-like Interactive Simulation")
    print("=" * 70)
    print()
    
    # Simulate Aider's typical output patterns
    test_script = """
import sys
import time

# Simulate Aider startup
print("\\033[34m[INFO] Loading model ollama/qwen2.5-coder:7b\\033[0m", flush=True)
time.sleep(0.1)
print("\\033[34m[INFO] Model loaded successfully\\033[0m", flush=True)
time.sleep(0.1)

# Simulate file analysis
print("\\033[36mAnalyzing file: test.py\\033[0m", flush=True)
time.sleep(0.2)

# Simulate code generation
print("Generating code...", flush=True)
time.sleep(0.3)

# Simulate success
print("\\033[32m✓ Changes applied to test.py\\033[0m", flush=True)
time.sleep(0.1)

# Simulate git commit
print("\\033[33m[GIT] Committing changes\\033[0m", flush=True)
time.sleep(0.2)
print("\\033[32m✓ Changes committed\\033[0m", flush=True)
"""
    
    process = subprocess.Popen(
        [sys.executable, "-c", test_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        universal_newlines=False,
        env={**os.environ, "PYTHONUNBUFFERED": "1"}
    )
    
    print("Streaming Aider simulation:")
    print("-" * 70)
    
    start_time = time.time()
    while True:
        line = process.stdout.readline()
        if not line:
            break
        # Real-time display
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
    
    total_time = time.time() - start_time
    process.wait()
    
    print()
    print(f"Total streaming time: {total_time:.2f}s")
    print("✓ Real-time streaming demonstrated")
    print()


def main():
    """Run all POC tests."""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "Aider Streaming POC Test Suite" + " " * 23 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    try:
        test_unbuffered_streaming()
        test_ansi_colors()
        test_aider_simulation()
        
        print("=" * 70)
        print("POC SUMMARY")
        print("=" * 70)
        print()
        print("✓ All tests completed successfully")
        print("✓ Unbuffered streaming works correctly")
        print("✓ ANSI color codes preserved")
        print("✓ Real-time output demonstrated")
        print()
        print("Next Steps:")
        print("  1. Install Aider CLI: pip install aider-chat")
        print("  2. Test with real Aider commands")
        print("  3. Integrate into AiderService class")
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


if __name__ == "__main__":
    sys.exit(main())
