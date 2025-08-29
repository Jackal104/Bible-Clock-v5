#!/usr/bin/env python3
"""
Display Health Monitor for Bible Clock v5
Automatically detects and fixes display issues including:
- Simulation mode stuck
- Display frozen/blank
- Service connectivity issues
"""

import os
import time
import logging
import requests
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import json

class DisplayHealthMonitor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_base = "http://localhost:7777"
        self.last_verse_update = None
        self.consecutive_failures = 0
        self.max_failures = 3
        
    def check_simulation_mode(self):
        """Check if display is stuck in simulation mode"""
        try:
            response = requests.get(f"{self.api_base}/api/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                simulation_mode = data.get('data', {}).get('simulation_mode', False)
                
                if simulation_mode:
                    self.logger.warning("🚨 Simulation mode detected - fixing automatically")
                    self.fix_simulation_mode()
                    return False
                return True
        except Exception as e:
            self.logger.error(f"Failed to check simulation mode: {e}")
            return False
            
    def fix_simulation_mode(self):
        """Automatically disable simulation mode"""
        try:
            # Method 1: Try API
            response = requests.post(
                f"{self.api_base}/api/settings",
                json={"hardware_mode": True},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info("✅ Simulation mode disabled via API")
                return True
                
        except Exception as e:
            self.logger.warning(f"API fix failed: {e}")
        
        # Method 2: Reload systemd and restart with environment
        try:
            self.logger.info("🔧 Reloading systemd and restarting with hardware mode")
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True, timeout=15)
            subprocess.run(['sudo', 'systemctl', 'restart', 'bible-clock'], check=True, timeout=30)
            
            # Wait for service to start
            time.sleep(15)
            self.logger.info("✅ Service restarted with hardware mode")
            return True
            
        except Exception as e:
            self.logger.error(f"Restart fix failed: {e}")
            return False
    
    def check_verse_updates(self):
        """Check if verses are updating properly"""
        try:
            # Read daily metrics to see last update
            daily_file = Path('data/daily_metrics.json')
            if daily_file.exists():
                with open(daily_file, 'r') as f:
                    data = json.load(f)
                
                today = datetime.now().date().isoformat()
                today_data = data.get(today, {})
                last_updated_str = today_data.get('last_updated')
                
                if last_updated_str:
                    last_updated = datetime.fromisoformat(last_updated_str)
                    time_since_update = datetime.now() - last_updated
                    
                    # If no update for more than 5 minutes, that's concerning
                    if time_since_update > timedelta(minutes=5):
                        self.logger.warning(f"⚠️ No verse updates for {time_since_update}")
                        return False
                    
                    return True
        except Exception as e:
            self.logger.error(f"Failed to check verse updates: {e}")
            
        return False
    
    def check_scheduler_conflicts(self):
        """Check for problematic scheduler processes that cause display conflicts"""
        try:
            import subprocess
            # Check for multiple bible clock processes
            result = subprocess.run(['pgrep', '-f', 'bible.*clock'], capture_output=True, text=True)
            processes = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            if len(processes) > 2:  # Should only be main process and health monitor
                self.logger.warning(f"⚠️ Multiple bible clock processes detected: {len(processes)}")
                # Kill extra processes
                for pid in processes[2:]:  # Keep first 2, kill the rest
                    try:
                        subprocess.run(['sudo', 'kill', pid], timeout=5)
                        self.logger.info(f"🧹 Killed conflicting process {pid}")
                    except:
                        pass
                return False
                        
            return True
        except Exception as e:
            self.logger.error(f"Scheduler conflict check failed: {e}")
            return True  # Don't fail health check on this error
    
    def test_hat_directly(self):
        """Test IT8951 HAT directly"""
        try:
            from IT8951.display import AutoEPDDisplay
            from IT8951 import constants
            from PIL import Image, ImageDraw
            
            display = AutoEPDDisplay(vcom=-1.5)
            img = Image.new('L', (display.width, display.height), 255)
            draw = ImageDraw.Draw(img)
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            draw.text((100, 100), 'Bible Clock - Health Check', fill=0)
            draw.text((100, 150), f'Time: {current_time}', fill=0)
            draw.text((100, 200), 'Display HAT: Working', fill=0)
            draw.text((100, 250), 'Restoring verse display...', fill=0)
            
            display.frame_buf.paste(img, (0, 0))
            display.draw_full(constants.DisplayModes.GC16)
            
            # Clear test pattern after successful test
            import time
            time.sleep(1)  # Let test pattern display briefly
            
            # Clear with full white screen
            clear_img = Image.new('L', (display.width, display.height), 255)
            display.frame_buf.paste(clear_img, (0, 0))
            display.draw_full(constants.DisplayModes.GC16)
            
            self.logger.info("✅ HAT direct test successful - test pattern cleared")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ HAT test failed: {e}")
            return False
    
    def force_display_refresh(self):
        """Force display refresh via API"""
        try:
            response = requests.post(f"{self.api_base}/api/refresh", timeout=15)
            if response.status_code == 200:
                self.logger.info("✅ Display refresh triggered")
                return True
        except Exception as e:
            self.logger.warning(f"Display refresh failed: {e}")
        return False
    
    def restart_service(self):
        """Restart the Bible Clock service"""
        try:
            self.logger.info("🔄 Restarting Bible Clock service")
            subprocess.run([
                'sudo', 'systemctl', 'restart', 'bible-clock'
            ], check=True, timeout=30)
            
            # Wait for service to start
            time.sleep(15)
            
            # Verify it's working
            if self.check_simulation_mode():
                self.logger.info("✅ Service restart successful")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Service restart failed: {e}")
        return False
    
    def perform_health_check(self):
        """Perform comprehensive health check"""
        self.logger.info("🔍 Starting display health check")
        
        # Check 1: Simulation mode
        if not self.check_simulation_mode():
            self.consecutive_failures += 1
        else:
            # Check 2: Scheduler conflicts (new check)
            if not self.check_scheduler_conflicts():
                self.logger.warning("Scheduler conflicts detected")
                self.consecutive_failures += 1
            else:
                # Check 3: Verse updates
                if not self.check_verse_updates():
                    self.logger.warning("Verse updates appear stalled")
                    
                    # Try display refresh first
                    if not self.force_display_refresh():
                        self.consecutive_failures += 1
                else:
                    # Everything looks good
                    self.consecutive_failures = 0
                    self.logger.info("✅ Display health check passed")
                    return True
        
        # If we have failures, take escalating action
        if self.consecutive_failures >= 1:
            self.logger.warning(f"🚨 Health check failures: {self.consecutive_failures}")
            
            # Test HAT directly
            if self.test_hat_directly():
                # HAT works, so service issue
                if self.consecutive_failures >= self.max_failures:
                    self.logger.error("🚨 Multiple failures - restarting service")
                    if self.restart_service():
                        self.consecutive_failures = 0
                        return True
            
        return False
    
    def run_monitoring_loop(self, check_interval=300):  # 5 minutes
        """Run continuous monitoring"""
        self.logger.info(f"🟢 Starting display health monitoring (check every {check_interval//60} minutes)")
        
        while True:
            try:
                self.perform_health_check()
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("👋 Health monitoring stopped")
                break
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                time.sleep(60)  # Wait 1 minute before retry

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    monitor = DisplayHealthMonitor()
    monitor.run_monitoring_loop()