#!/usr/bin/env python3
"""
CPU Monitor for Bible Clock
Monitors CPU usage and automatically restarts the service when usage is too high
"""

import psutil
import subprocess
import time
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/admin/Bible-Clock-v4/logs/cpu_monitor.log'),
        logging.StreamHandler()
    ]
)

class BibleClockMonitor:
    def __init__(self):
        self.process_name = "python3"
        self.script_path = "/home/admin/Bible-Clock-v4/src/main.py"
        self.max_cpu_threshold = 25.0  # Restart if CPU > 25% for sustained period
        self.max_memory_threshold = 300  # Restart if memory > 300MB
        self.check_interval = 30  # Check every 30 seconds
        self.high_usage_count = 0
        self.restart_threshold = 5  # Restart after 5 consecutive high readings
        
    def find_bible_clock_process(self):
        """Find the Bible Clock process"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
            try:
                if (proc.info['name'] == self.process_name and 
                    proc.info['cmdline'] and 
                    any('main.py' in cmd or 'bible' in cmd.lower() for cmd in proc.info['cmdline'])):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def restart_bible_clock(self):
        """Restart the Bible Clock service"""
        logging.info("Restarting Bible Clock due to high resource usage...")
        
        # Kill existing process
        proc = self.find_bible_clock_process()
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=10)
                logging.info(f"Terminated process {proc.pid}")
            except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                try:
                    proc.kill()
                    logging.info(f"Force killed process {proc.pid}")
                except psutil.NoSuchProcess:
                    pass
        
        # Wait a moment
        time.sleep(2)
        
        # Start new process
        try:
            subprocess.Popen([
                'python3', 
                '/home/admin/Bible-Clock-v4/src/main.py'
            ], cwd='/home/admin/Bible-Clock-v4')
            logging.info("Bible Clock restarted successfully")
            self.high_usage_count = 0
        except Exception as e:
            logging.error(f"Failed to restart Bible Clock: {e}")
    
    def monitor(self):
        """Main monitoring loop"""
        logging.info("Starting Bible Clock CPU monitor...")
        
        while True:
            try:
                proc = self.find_bible_clock_process()
                
                if not proc:
                    logging.warning("Bible Clock process not found, starting it...")
                    self.restart_bible_clock()
                    time.sleep(self.check_interval)
                    continue
                
                # Get current usage
                cpu_percent = proc.cpu_percent()
                memory_mb = proc.memory_info().rss / 1024 / 1024
                
                logging.info(f"Bible Clock PID {proc.pid}: CPU {cpu_percent:.1f}%, Memory {memory_mb:.1f}MB")
                
                # Check if usage is too high
                if cpu_percent > self.max_cpu_threshold or memory_mb > self.max_memory_threshold:
                    self.high_usage_count += 1
                    logging.warning(f"High resource usage detected ({self.high_usage_count}/{self.restart_threshold})")
                    
                    if self.high_usage_count >= self.restart_threshold:
                        self.restart_bible_clock()
                else:
                    self.high_usage_count = 0
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logging.info("Monitor stopped by user")
                break
            except Exception as e:
                logging.error(f"Monitor error: {e}")
                time.sleep(self.check_interval)

if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs('/home/admin/Bible-Clock-v4/logs', exist_ok=True)
    
    monitor = BibleClockMonitor()
    monitor.monitor()