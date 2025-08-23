#!/usr/bin/env python3
"""
Emergency memory cleanup script for Bible Clock
Run this if memory usage gets too high
"""

import gc
import os
import signal
import psutil
import logging

def force_cleanup():
    """Force garbage collection and memory cleanup."""
    print("Starting emergency memory cleanup...")
    
    # Force garbage collection multiple times
    for i in range(3):
        collected = gc.collect()
        print(f"Garbage collection round {i+1}: {collected} objects collected")
    
    # Get current memory usage
    try:
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        print(f"Current memory usage: {memory_mb:.1f}MB")
        
        # Check system memory
        system_memory = psutil.virtual_memory()
        print(f"System memory: {system_memory.percent:.1f}% used")
        
    except Exception as e:
        print(f"Could not get memory info: {e}")

def find_bible_clock_process():
    """Find the main Bible Clock process."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == 'python3' and proc.info['cmdline']:
                cmdline_str = ' '.join(proc.info['cmdline'])
                if any(keyword in cmdline_str for keyword in ['main.py', 'Bible-Clock-v4', '--enable-voice']):
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def send_cleanup_signal():
    """Send a signal to Bible Clock to trigger cleanup."""
    proc = find_bible_clock_process()
    if proc:
        try:
            # Send SIGUSR1 to trigger cleanup (if implemented)
            os.kill(proc.pid, signal.SIGUSR1)
            print(f"Sent cleanup signal to Bible Clock process {proc.pid}")
        except Exception as e:
            print(f"Could not send signal: {e}")
    else:
        print("Bible Clock process not found")

if __name__ == "__main__":
    force_cleanup()
    send_cleanup_signal()
    print("Emergency cleanup completed")