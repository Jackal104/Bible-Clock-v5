#!/usr/bin/env python3
"""
Display Schedule Manager for Bible Clock
Manages daily on/off scheduling for the display with per-day time controls
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import schedule as schedule_lib

logger = logging.getLogger(__name__)

class DisplayScheduleManager:
    """Manages display scheduling with daily on/off times and enable/disable controls."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.schedule_file = self.data_dir / "display_schedule.json"
        self.lock = threading.Lock()
        self.running = False
        self.schedule_thread = None
        
        # Display state tracking
        self.display_enabled = True
        self.last_schedule_check = datetime.now()
        
        # Default schedule (all days enabled, 7 AM to 11 PM)
        self.default_schedule = {
            "monday": {"enabled": True, "time_on": "07:00", "time_off": "23:00"},
            "tuesday": {"enabled": True, "time_on": "07:00", "time_off": "23:00"},
            "wednesday": {"enabled": True, "time_on": "07:00", "time_off": "23:00"},
            "thursday": {"enabled": True, "time_on": "07:00", "time_off": "23:00"},
            "friday": {"enabled": True, "time_on": "07:00", "time_off": "23:00"},
            "saturday": {"enabled": True, "time_on": "07:00", "time_off": "23:00"},
            "sunday": {"enabled": True, "time_on": "07:00", "time_off": "23:00"}
        }
        
        # Callbacks for display control
        self.display_on_callback = None
        self.display_off_callback = None
        
        # Load existing schedule
        self.schedule_data = self._load_schedule()
        
        logger.info("Display Schedule Manager initialized")
    
    def set_display_callbacks(self, on_callback, off_callback):
        """Set callbacks for turning display on/off."""
        self.display_on_callback = on_callback
        self.display_off_callback = off_callback
    
    def _load_schedule(self) -> Dict[str, Any]:
        """Load schedule from file or create default."""
        try:
            if self.schedule_file.exists():
                with open(self.schedule_file, 'r') as f:
                    data = json.load(f)
                    
                # Validate loaded data has all days
                for day in self.default_schedule.keys():
                    if day not in data:
                        data[day] = self.default_schedule[day].copy()
                
                logger.info("Loaded existing display schedule")
                return data
            else:
                logger.info("Creating default display schedule")
                return self.default_schedule.copy()
                
        except Exception as e:
            logger.error(f"Failed to load schedule, using default: {e}")
            return self.default_schedule.copy()
    
    def _save_schedule(self):
        """Save current schedule to file."""
        try:
            with self.lock:
                schedule_to_save = {
                    **self.schedule_data,
                    "last_updated": datetime.now().isoformat(),
                    "timezone": str(datetime.now().astimezone().tzinfo)
                }
                
                with open(self.schedule_file, 'w') as f:
                    json.dump(schedule_to_save, f, indent=2)
                    
            logger.info("Display schedule saved")
            
        except Exception as e:
            logger.error(f"Failed to save schedule: {e}")
    
    def get_schedule(self) -> Dict[str, Any]:
        """Get current schedule configuration."""
        with self.lock:
            return {
                "schedule": self.schedule_data.copy(),
                "display_enabled": self.display_enabled,
                "last_check": self.last_schedule_check.isoformat(),
                "current_status": self._get_current_status()
            }
    
    def update_schedule(self, schedule_data: Dict[str, Any]) -> bool:
        """Update schedule configuration."""
        try:
            with self.lock:
                # Validate schedule data
                for day_name in self.default_schedule.keys():
                    if day_name in schedule_data:
                        day_config = schedule_data[day_name]
                        
                        # Validate required fields
                        if not all(key in day_config for key in ['enabled', 'time_on', 'time_off']):
                            logger.error(f"Invalid schedule data for {day_name}: missing required fields")
                            return False
                        
                        # Validate time format
                        try:
                            datetime.strptime(day_config['time_on'], '%H:%M')
                            datetime.strptime(day_config['time_off'], '%H:%M')
                        except ValueError:
                            logger.error(f"Invalid time format for {day_name}")
                            return False
                        
                        self.schedule_data[day_name] = {
                            "enabled": bool(day_config['enabled']),
                            "time_on": day_config['time_on'],
                            "time_off": day_config['time_off']
                        }
                
                self._save_schedule()
                self._setup_schedule_jobs()  # Recreate schedule jobs
                
                logger.info("Display schedule updated successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update schedule: {e}")
            return False
    
    def _get_current_status(self) -> Dict[str, Any]:
        """Get current schedule status."""
        now = datetime.now()
        day_name = now.strftime('%A').lower()
        current_time = now.strftime('%H:%M')
        
        day_config = self.schedule_data.get(day_name, self.default_schedule[day_name])
        
        should_be_on = False
        if day_config['enabled']:
            time_on = day_config['time_on']
            time_off = day_config['time_off']
            
            # Handle cases where off time is next day (e.g., 23:00 to 07:00)
            if time_on <= time_off:
                # Same day schedule (e.g., 07:00 to 23:00)
                should_be_on = time_on <= current_time <= time_off
            else:
                # Overnight schedule (e.g., 23:00 to 07:00)
                should_be_on = current_time >= time_on or current_time <= time_off
        
        return {
            "day": day_name,
            "current_time": current_time,
            "day_enabled": day_config['enabled'],
            "time_on": day_config['time_on'],
            "time_off": day_config['time_off'],
            "should_be_on": should_be_on,
            "display_enabled": self.display_enabled
        }
    
    def _setup_schedule_jobs(self):
        """Set up all schedule jobs for the week."""
        # Clear existing schedule jobs
        schedule_lib.clear()
        
        for day_name, config in self.schedule_data.items():
            if config['enabled']:
                day_mapping = {
                    'monday': schedule_lib.every().monday,
                    'tuesday': schedule_lib.every().tuesday,
                    'wednesday': schedule_lib.every().wednesday,
                    'thursday': schedule_lib.every().thursday,
                    'friday': schedule_lib.every().friday,
                    'saturday': schedule_lib.every().saturday,
                    'sunday': schedule_lib.every().sunday
                }
                
                scheduler = day_mapping[day_name]
                
                # Schedule display ON
                scheduler.at(config['time_on']).do(self._schedule_display_on, day_name)
                
                # Schedule display OFF
                scheduler.at(config['time_off']).do(self._schedule_display_off, day_name)
        
        logger.info("Schedule jobs configured for all enabled days")
    
    def _schedule_display_on(self, day_name: str):
        """Execute scheduled display turn-on."""
        logger.info(f"Scheduled display ON for {day_name}")
        self.turn_display_on(scheduled=True)
    
    def _schedule_display_off(self, day_name: str):
        """Execute scheduled display turn-off."""
        logger.info(f"Scheduled display OFF for {day_name}")
        self.turn_display_off(scheduled=True)
    
    def turn_display_on(self, scheduled: bool = False):
        """Turn display on and start showing content."""
        try:
            self.display_enabled = True
            
            if self.display_on_callback:
                self.display_on_callback()
            
            # Track hardware event
            event_type = "scheduled_display_on" if scheduled else "manual_display_on"
            self._track_hardware_event(event_type, "Display turned on")
            
            logger.info(f"Display turned ON ({'scheduled' if scheduled else 'manual'})")
            
        except Exception as e:
            logger.error(f"Failed to turn display on: {e}")
    
    def turn_display_off(self, scheduled: bool = False):
        """Turn display off and clean screen."""
        try:
            self.display_enabled = False
            
            if self.display_off_callback:
                self.display_off_callback()
            
            # Track hardware event
            event_type = "scheduled_display_off" if scheduled else "manual_display_off"
            self._track_hardware_event(event_type, "Display turned off")
            
            logger.info(f"Display turned OFF ({'scheduled' if scheduled else 'manual'})")
            
        except Exception as e:
            logger.error(f"Failed to turn display off: {e}")
    
    def _track_hardware_event(self, event_type: str, description: str):
        """Track display schedule events in metrics."""
        try:
            # This will be connected to the main metrics system
            from bible_clock_metrics import BibleClockMetrics
            # Note: This would need to be injected from the service manager
            pass
        except ImportError:
            pass
    
    def start_scheduler(self):
        """Start the background scheduler thread."""
        if self.running:
            return
        
        self.running = True
        self._setup_schedule_jobs()
        
        def run_scheduler():
            while self.running:
                try:
                    schedule_lib.run_pending()
                    self.last_schedule_check = datetime.now()
                    time.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    logger.error(f"Schedule check error: {e}")
                    time.sleep(60)  # Wait longer on error
        
        self.schedule_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.schedule_thread.start()
        
        logger.info("Display scheduler started")
    
    def stop_scheduler(self):
        """Stop the background scheduler."""
        self.running = False
        if self.schedule_thread and self.schedule_thread.is_alive():
            self.schedule_thread.join(timeout=5)
        
        schedule_lib.clear()
        logger.info("Display scheduler stopped")
    
    def is_display_scheduled_on(self) -> bool:
        """Check if display should be on according to current schedule."""
        status = self._get_current_status()
        return status['should_be_on']
    
    def get_next_schedule_event(self) -> Optional[Dict[str, Any]]:
        """Get information about the next scheduled event."""
        try:
            now = datetime.now()
            next_events = []
            
            for day_name, config in self.schedule_data.items():
                if not config['enabled']:
                    continue
                
                # Calculate next occurrence of this day
                days_ahead = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].index(day_name) - now.weekday()
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                
                target_date = now + timedelta(days=days_ahead)
                
                # Add ON event
                on_time = datetime.strptime(config['time_on'], '%H:%M').time()
                on_datetime = datetime.combine(target_date.date(), on_time)
                if on_datetime > now:
                    next_events.append({
                        'event': 'display_on',
                        'day': day_name,
                        'time': config['time_on'],
                        'datetime': on_datetime,
                        'description': f"Display ON - {day_name.title()} at {config['time_on']}"
                    })
                
                # Add OFF event
                off_time = datetime.strptime(config['time_off'], '%H:%M').time()
                off_datetime = datetime.combine(target_date.date(), off_time)
                if off_datetime > now:
                    next_events.append({
                        'event': 'display_off',
                        'day': day_name,
                        'time': config['time_off'],
                        'datetime': off_datetime,
                        'description': f"Display OFF - {day_name.title()} at {config['time_off']}"
                    })
            
            if next_events:
                next_event = min(next_events, key=lambda x: x['datetime'])
                next_event['time_until'] = str(next_event['datetime'] - now).split('.')[0]  # Remove microseconds
                return next_event
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get next schedule event: {e}")
            return None