#!/usr/bin/env python3
"""
Unified System Monitor for Bible Clock
Monitors CPU usage, memory usage, and system health with automatic service management
"""

import psutil
import subprocess
import time
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/admin/Bible-Clock-v4/logs/system_monitor.log'),
        logging.StreamHandler()
    ]
)

class BibleClockSystemMonitor:
    def __init__(self):
        self.process_name = "python3"
        self.script_path = "/home/admin/Bible-Clock-v4/main.py"
        self.service_name = "bible-clock"
        
        # Thresholds - Realistic for dedicated Bible Clock device  
        self.max_cpu_threshold = 50.0  # Restart if CPU > 50% sustained (allows spikes)
        self.max_memory_threshold_mb = 650  # Restart if memory > 650MB (70% of 1GB)
        self.max_memory_threshold_percent = 85.0  # Restart if system memory > 85%
        
        # Check intervals
        self.check_interval = 30  # Check every 30 seconds
        self.health_check_interval = 300  # Health check every 5 minutes
        
        # Consecutive threshold tracking
        self.high_usage_count = 0
        self.restart_threshold = 6  # Restart after 6 consecutive high readings (3 minutes)
        
        # Performance tracking
        self.last_health_check = datetime.now()
        self.restart_count = 0
        self.start_time = datetime.now()
        
        # System metrics tracking
        self.cpu_history = []
        self.memory_history = []
        self.max_history_length = 20  # Keep last 20 readings
        
    def find_bible_clock_process(self):
        """Find the Bible Clock process"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info', 'create_time']):
            try:
                if proc.info['name'] == self.process_name and proc.info['cmdline']:
                    cmdline_str = ' '.join(proc.info['cmdline'])
                    # Look for main.py or --enable-voice but exclude system_monitor.py
                    if (any(keyword in cmdline_str for keyword in ['main.py', '--enable-voice']) and 
                        'system_monitor.py' not in cmdline_str):
                        logging.info(f"Found Bible Clock process: PID {proc.info['pid']}, CMD: {cmdline_str}")
                        return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def get_system_metrics(self):
        """Get overall system metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'system_cpu': cpu_percent,
                'system_memory_percent': memory.percent,
                'system_memory_used_gb': memory.used / (1024**3),
                'system_memory_total_gb': memory.total / (1024**3),
                'disk_percent': disk.percent,
                'disk_used_gb': disk.used / (1024**3),
                'disk_total_gb': disk.total / (1024**3)
            }
        except Exception as e:
            logging.error(f"Failed to get system metrics: {e}")
            return {}
    
    def restart_bible_clock(self):
        """Restart the Bible Clock service"""
        logging.warning(f"Restarting Bible Clock due to high resource usage (attempt #{self.restart_count + 1})")
        
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
        time.sleep(3)
        
        # Try systemctl first, then direct start
        try:
            # Try systemctl restart
            result = subprocess.run(['systemctl', 'is-active', self.service_name], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                subprocess.run(['sudo', 'systemctl', 'restart', self.service_name], 
                             timeout=30, check=True)
                logging.info("Bible Clock restarted via systemctl")
            else:
                raise subprocess.SubprocessError("Systemctl not available")
                
        except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
            # Fallback to direct process start
            try:
                subprocess.Popen([
                    'python3', 
                    '/home/admin/Bible-Clock-v4/main.py'
                ], cwd='/home/admin/Bible-Clock-v4')
                logging.info("Bible Clock restarted directly")
            except Exception as e:
                logging.error(f"Failed to restart Bible Clock: {e}")
                return False
        
        self.high_usage_count = 0
        self.restart_count += 1
        logging.info(f"Bible Clock restart completed (total restarts: {self.restart_count})")
        return True
    
    def check_service_health(self):
        """Perform comprehensive health check"""
        proc = self.find_bible_clock_process()
        if not proc:
            logging.warning("Bible Clock process not found, attempting restart...")
            return self.restart_bible_clock()
        
        try:
            # Check if process is responsive
            if proc.status() == psutil.STATUS_ZOMBIE:
                logging.warning("Bible Clock process is zombie, restarting...")
                return self.restart_bible_clock()
            
            # Check process uptime
            create_time = datetime.fromtimestamp(proc.info['create_time'])
            uptime = datetime.now() - create_time
            
            # Log health status
            logging.info(f"Health check: PID {proc.pid}, Status: {proc.status()}, Uptime: {uptime}")
            
            # Check for very long running processes (potential memory leaks)
            if uptime > timedelta(hours=24) and self.restart_count == 0:
                logging.info("Process has been running for >24h, considering preventive restart")
                # Don't auto-restart, just log for now
            
            return True
            
        except Exception as e:
            logging.error(f"Health check failed: {e}")
            return False
    
    def update_performance_history(self, cpu_percent, memory_mb):
        """Update performance history for trend analysis"""
        self.cpu_history.append(cpu_percent)
        self.memory_history.append(memory_mb)
        
        # Keep only recent history
        if len(self.cpu_history) > self.max_history_length:
            self.cpu_history.pop(0)
        if len(self.memory_history) > self.max_history_length:
            self.memory_history.pop(0)
    
    def get_performance_trends(self):
        """Analyze performance trends"""
        if len(self.cpu_history) < 5:
            return {}
        
        avg_cpu = sum(self.cpu_history) / len(self.cpu_history)
        avg_memory = sum(self.memory_history) / len(self.memory_history)
        max_cpu = max(self.cpu_history)
        max_memory = max(self.memory_history)
        
        return {
            'avg_cpu': avg_cpu,
            'avg_memory_mb': avg_memory,
            'max_cpu': max_cpu,
            'max_memory_mb': max_memory,
            'samples': len(self.cpu_history)
        }
    
    def monitor(self):
        """Main monitoring loop"""
        logging.info("Starting Bible Clock System Monitor...")
        logging.info(f"CPU threshold: {self.max_cpu_threshold}%, Memory threshold: {self.max_memory_threshold_mb}MB")
        
        while True:
            try:
                # Health check every 5 minutes
                if datetime.now() - self.last_health_check > timedelta(seconds=self.health_check_interval):
                    self.check_service_health()
                    self.last_health_check = datetime.now()
                
                # Find Bible Clock process
                proc = self.find_bible_clock_process()
                
                if not proc:
                    logging.warning("Bible Clock process not found, attempting restart...")
                    self.restart_bible_clock()
                    time.sleep(self.check_interval)
                    continue
                
                # Get current usage
                cpu_percent = proc.cpu_percent()
                memory_mb = proc.memory_info().rss / 1024 / 1024
                
                # Get system metrics
                system_metrics = self.get_system_metrics()
                
                # Update performance history
                self.update_performance_history(cpu_percent, memory_mb)
                
                # Log current status
                uptime = datetime.now() - datetime.fromtimestamp(proc.create_time())
                logging.info(f"Bible Clock PID {proc.pid}: CPU {cpu_percent:.1f}%, Memory {memory_mb:.1f}MB, Uptime: {uptime}")
                
                # Check system metrics
                if system_metrics:
                    logging.info(f"System: CPU {system_metrics.get('system_cpu', 0):.1f}%, "
                               f"Memory {system_metrics.get('system_memory_percent', 0):.1f}%, "
                               f"Disk {system_metrics.get('disk_percent', 0):.1f}%")
                
                # Check if usage is too high
                high_usage = (cpu_percent > self.max_cpu_threshold or 
                             memory_mb > self.max_memory_threshold_mb or
                             system_metrics.get('system_memory_percent', 0) > self.max_memory_threshold_percent)
                
                if high_usage:
                    self.high_usage_count += 1
                    reason = []
                    if cpu_percent > self.max_cpu_threshold:
                        reason.append(f"CPU {cpu_percent:.1f}%")
                    if memory_mb > self.max_memory_threshold_mb:
                        reason.append(f"Memory {memory_mb:.1f}MB")
                    if system_metrics.get('system_memory_percent', 0) > self.max_memory_threshold_percent:
                        reason.append(f"System Memory {system_metrics.get('system_memory_percent', 0):.1f}%")
                    
                    logging.warning(f"High resource usage detected ({self.high_usage_count}/{self.restart_threshold}): {', '.join(reason)}")
                    
                    if self.high_usage_count >= self.restart_threshold:
                        self.restart_bible_clock()
                else:
                    if self.high_usage_count > 0:
                        logging.info(f"Resource usage normalized - resetting counter (was {self.high_usage_count})")
                    self.high_usage_count = 0
                
                # Log performance trends periodically
                if len(self.cpu_history) >= self.max_history_length:
                    trends = self.get_performance_trends()
                    logging.info(f"Performance trends - Avg CPU: {trends['avg_cpu']:.1f}%, "
                               f"Avg Memory: {trends['avg_memory_mb']:.1f}MB, "
                               f"Max CPU: {trends['max_cpu']:.1f}%, "
                               f"Max Memory: {trends['max_memory_mb']:.1f}MB")
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logging.info("System monitor stopped by user")
                break
            except Exception as e:
                logging.error(f"Monitor error: {e}")
                time.sleep(self.check_interval)

if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs('/home/admin/Bible-Clock-v4/logs', exist_ok=True)
    
    monitor = BibleClockSystemMonitor()
    monitor.monitor()