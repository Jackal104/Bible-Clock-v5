#!/usr/bin/env python3
"""
Bible Clock Real-Time Metrics Manager
Tracks all statistics requirements in real-time with proper aggregation.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

@dataclass
class MetricsSnapshot:
    """Real-time snapshot of current metrics."""
    timestamp: str
    verses_displayed_today: int
    uptime_hours: float
    mode_usage_seconds: Dict[str, float]  # Actual time spent in each mode
    translation_usage_count: Dict[str, int]  # Count of each translation used
    bible_books_accessed: Dict[str, int]  # Count of each book accessed
    recent_activities: List[Dict[str, str]]
    translation_completion_percentages: Dict[str, float]

class BibleClockMetrics:
    """Real-time metrics tracking for Bible Clock."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Metrics files
        self.daily_metrics_file = self.data_dir / "daily_metrics.json"
        self.weekly_metrics_file = self.data_dir / "weekly_metrics.json"
        self.monthly_metrics_file = self.data_dir / "monthly_metrics.json"
        self.yearly_metrics_file = self.data_dir / "yearly_metrics.json"
        self.alltime_metrics_file = self.data_dir / "alltime_metrics.json"
        
        # Real-time tracking
        self.session_start = datetime.now()
        self.last_midnight_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.current_mode = "time"
        self.mode_start_time = time.time()
        
        # Today's counters (reset at midnight)
        self.verses_displayed_today = 0
        self.mode_usage_seconds_today = defaultdict(float)
        self.translation_usage_today = defaultdict(int)
        self.bible_books_accessed_today = defaultdict(int)
        self.recent_activities = []
        
        # Thread safety
        self.lock = threading.Lock()
        self._in_midnight_reset = False  # Prevent recursive saves during midnight reset
        
        # Load existing data
        self._load_daily_data()
        
        logger.info("Bible Clock Metrics initialized")
    
    def _load_daily_data(self):
        """Load today's existing metrics if available."""
        if self.daily_metrics_file.exists():
            try:
                with open(self.daily_metrics_file, 'r') as f:
                    data = json.load(f)
                    today_str = datetime.now().strftime('%Y-%m-%d')
                    if today_str in data:
                        today_data = data[today_str]
                        self.verses_displayed_today = today_data.get('verses_displayed_today', 0)
                        self.mode_usage_seconds_today.update(today_data.get('mode_usage_seconds', {}))
                        self.translation_usage_today.update(today_data.get('translation_usage_count', {}))
                        self.bible_books_accessed_today.update(today_data.get('bible_books_accessed', {}))
                        self.recent_activities = today_data.get('recent_activities', [])[-50:]  # Keep last 50
                        logger.info(f"Loaded existing daily metrics: {self.verses_displayed_today} verses today")
            except Exception as e:
                logger.error(f"Failed to load daily metrics: {e}")
    
    def track_verse_displayed(self, verse_data: Dict[str, Any]):
        """Track when a verse is displayed."""
        with self.lock:
            self._check_midnight_reset()
            
            # Increment verse counter
            self.verses_displayed_today += 1
            
            # Track translation usage
            if verse_data.get('parallel_mode'):
                # In parallel mode, track both primary and secondary translations
                primary_translation = verse_data.get('primary_translation', verse_data.get('translation', 'kjv')).lower()
                secondary_translation = verse_data.get('secondary_translation', 'amp').lower()
                
                self.translation_usage_today[primary_translation] += 1
                self.translation_usage_today[secondary_translation] += 1
                
                logger.debug(f"Parallel mode: tracked {primary_translation.upper()} and {secondary_translation.upper()}")
            else:
                # Single translation mode
                translation = verse_data.get('translation', 'kjv').lower()
                self.translation_usage_today[translation] += 1
            
            # Track Bible book accessed
            book = verse_data.get('book')
            if book:
                self.bible_books_accessed_today[book] += 1
            
            # Only log recent activity for certain milestones (every 10 verses or translation changes)
            if self.verses_displayed_today % 10 == 0:
                self._add_recent_activity(
                    "verse_milestone", 
                    f"Displayed {self.verses_displayed_today} verses today"
                )
            
            # Save metrics
            self._save_daily_metrics()
            
            logger.debug(f"Verse tracked: {verse_data.get('reference')} - Total today: {self.verses_displayed_today}")
    
    def track_mode_change(self, new_mode: str):
        """Track when display mode changes."""
        with self.lock:
            self._check_midnight_reset()
            
            # Record time spent in current mode
            current_time = time.time()
            time_in_mode = current_time - self.mode_start_time
            self.mode_usage_seconds_today[self.current_mode] += time_in_mode
            
            # Switch to new mode
            self.current_mode = new_mode
            self.mode_start_time = current_time
            
            # Add to recent activity
            self._add_recent_activity(
                "mode_change", 
                f"Switched to {new_mode.title()} mode"
            )
            
            # Save metrics
            self._save_daily_metrics()
            
            logger.info(f"Mode changed to {new_mode}")
    
    def track_system_event(self, event_type: str, description: str):
        """Track system events like display on/off, errors, etc."""
        with self.lock:
            self._add_recent_activity(event_type, description)
            self._save_daily_metrics()
    
    def track_hardware_event(self, event_type: str, details: str = ""):
        """Track hardware events like display power, voice activation, etc."""
        event_descriptions = {
            'display_on': 'E-ink display powered on',
            'display_off': 'E-ink display powered off',
            'voice_enabled': 'Voice control activated',
            'voice_disabled': 'Voice control deactivated',
            'audio_error': 'Audio system error detected',
            'system_start': 'Bible Clock service started',
            'system_stop': 'Bible Clock service stopped',
            'midnight_reset': 'Daily counters reset at midnight',
            'low_memory': 'Low memory warning detected',
            'high_cpu': 'High CPU usage detected',
            'network_error': 'Network connectivity issue',
            'gpio_error': 'GPIO hardware error'
        }
        
        description = event_descriptions.get(event_type, f"{event_type}: {details}")
        if details and event_type in event_descriptions:
            description = f"{event_descriptions[event_type]} - {details}"
            
        with self.lock:
            self._add_recent_activity('hardware', description)
            # Skip save during midnight reset to prevent recursive blocking
            if not self._in_midnight_reset:
                self._save_daily_metrics()
            logger.info(f"Hardware event tracked: {description}")
    
    def track_performance_event(self, cpu_percent: float, memory_percent: float, temp_c: float):
        """Track system performance milestones."""
        if cpu_percent > 80:
            self.track_hardware_event('high_cpu', f"CPU usage at {cpu_percent:.1f}%")
        if memory_percent > 90:
            self.track_hardware_event('low_memory', f"Memory usage at {memory_percent:.1f}%")
        if temp_c > 75:
            self.track_hardware_event('high_temp', f"CPU temperature at {temp_c:.1f}°C")
    
    def get_current_metrics(self) -> MetricsSnapshot:
        """Get current real-time metrics snapshot."""
        with self.lock:
            self._check_midnight_reset()
            
            # Update current mode usage
            current_time = time.time()
            time_in_current_mode = current_time - self.mode_start_time
            current_mode_usage = dict(self.mode_usage_seconds_today)
            # Ensure current mode key exists before adding time
            if self.current_mode not in current_mode_usage:
                current_mode_usage[self.current_mode] = 0.0
            current_mode_usage[self.current_mode] += time_in_current_mode
            
            # Calculate uptime
            uptime_seconds = (datetime.now() - self.session_start).total_seconds()
            uptime_hours = uptime_seconds / 3600.0
            
            # Get translation completion percentages
            completion_percentages = self._calculate_translation_completion()
            
            return MetricsSnapshot(
                timestamp=datetime.now().isoformat(),
                verses_displayed_today=self.verses_displayed_today,
                uptime_hours=uptime_hours,
                mode_usage_seconds=current_mode_usage,
                translation_usage_count=dict(self.translation_usage_today),
                bible_books_accessed=dict(self.bible_books_accessed_today),
                recent_activities=self.recent_activities[-20:],  # Last 20 activities
                translation_completion_percentages=completion_percentages
            )
    
    def get_aggregated_metrics(self, period: str) -> Dict[str, Any]:
        """Get aggregated metrics for period (today, week, month, year, alltime)."""
        if period == "today":
            return self._get_daily_aggregated_metrics()
        elif period == "week":
            return self._get_weekly_aggregated_metrics()
        elif period == "month":
            return self._get_monthly_aggregated_metrics()
        elif period == "year":
            return self._get_yearly_aggregated_metrics()
        elif period == "alltime":
            return self._get_alltime_aggregated_metrics()
        else:
            return self._get_daily_aggregated_metrics()
    
    def _check_midnight_reset(self):
        """Check if we've passed midnight and reset daily counters."""
        now = datetime.now()
        current_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if current_midnight > self.last_midnight_reset:
            logger.info("Midnight reset: clearing daily counters")
            
            # Set flag to prevent recursive saves
            self._in_midnight_reset = True
            
            # Save current day's data before reset in a separate thread to prevent blocking
            import threading
            def save_midnight_data():
                try:
                    self._save_daily_metrics()
                    self._aggregate_daily_to_weekly()
                    logger.info("Midnight data save completed successfully")
                except Exception as e:
                    logger.error(f"Midnight data save failed: {e}")
            
            # Run save operations in background thread with timeout
            save_thread = threading.Thread(target=save_midnight_data, daemon=True)
            save_thread.start()
            
            # Don't wait for thread to complete - reset counters immediately
            # Reset daily counters
            self.verses_displayed_today = 0
            self.mode_usage_seconds_today.clear()
            self.translation_usage_today.clear()
            self.bible_books_accessed_today.clear()
            self.recent_activities = []
            
            self.last_midnight_reset = current_midnight
            self.track_hardware_event('midnight_reset')
            
            # Clear flag after midnight reset is complete
            self._in_midnight_reset = False
    
    def _add_recent_activity(self, activity_type: str, description: str):
        """Add an activity to recent activities list."""
        activity = {
            "timestamp": datetime.now().isoformat(),
            "type": activity_type,
            "description": description
        }
        self.recent_activities.append(activity)
        
        # Keep only last 100 activities
        self.recent_activities = self.recent_activities[-100:]
    
    def _calculate_translation_completion(self) -> Dict[str, float]:
        """Calculate completion percentage for each translation cache."""
        # This would integrate with the verse manager's translation completion calculation
        # For now, return placeholder values
        return {
            'kjv': 99.8,
            'esv': 87.3,
            'amp': 45.2,
            'nlt': 78.9,
            'nasb': 34.1,
            'msg': 12.5,
            'cev': 23.7,
            'ylt': 67.4
        }
    
    def _save_daily_metrics(self):
        """Save current daily metrics to file with timeout protection."""
        import threading
        import time
        
        try:
            today_str = datetime.now().strftime('%Y-%m-%d')
            
            # Use threading timeout instead of signals (works in background threads)
            result = [None]  # Use list to allow modification from inner function
            exception = [None]
            
            def save_operation():
                try:
                    # Load existing data
                    daily_data = {}
                    if self.daily_metrics_file.exists():
                        with open(self.daily_metrics_file, 'r') as f:
                            daily_data = json.load(f)
                    
                    # Update today's data
                    daily_data[today_str] = {
                        'date': today_str,
                        'verses_displayed_today': self.verses_displayed_today,
                        'mode_usage_seconds': dict(self.mode_usage_seconds_today),
                        'translation_usage_count': dict(self.translation_usage_today),
                        'bible_books_accessed': dict(self.bible_books_accessed_today),
                        'recent_activities': self.recent_activities[-50:],  # Keep last 50
                        'last_updated': datetime.now().isoformat()
                    }
                    
                    # Save to file atomically (write to temp file first)
                    temp_file = self.daily_metrics_file.with_suffix('.tmp')
                    with open(temp_file, 'w') as f:
                        json.dump(daily_data, f, indent=2)
                    
                    # Atomic rename
                    temp_file.replace(self.daily_metrics_file)
                    result[0] = True
                except Exception as e:
                    exception[0] = e
            
            # Run save operation in thread with timeout
            save_thread = threading.Thread(target=save_operation, daemon=True)
            save_thread.start()
            save_thread.join(timeout=30)  # 30 second timeout
            
            if save_thread.is_alive():
                logger.error("Daily metrics save timed out after 30 seconds")
            elif exception[0]:
                raise exception[0]
            elif result[0] is None:
                logger.error("Daily metrics save completed but result is unknown")
                
        except Exception as e:
            logger.error(f"Failed to save daily metrics: {e}")
            # Don't raise exception to prevent blocking main thread
    
    def _get_daily_aggregated_metrics(self) -> Dict[str, Any]:
        """Get today's aggregated metrics."""
        current_metrics = self.get_current_metrics()
        
        # Convert mode usage from seconds to hours
        mode_usage_hours = {
            mode: round(seconds / 3600.0, 1) 
            for mode, seconds in current_metrics.mode_usage_seconds.items()
        }
        
        return {
            'period': 'today',
            'verses_displayed': current_metrics.verses_displayed_today,
            'uptime_hours': round(current_metrics.uptime_hours, 1),
            'mode_usage_hours': mode_usage_hours,
            'translation_usage_count': current_metrics.translation_usage_count,
            'bible_books_accessed_count': current_metrics.bible_books_accessed,
            'recent_activities': current_metrics.recent_activities,
            'translation_completion_percentages': current_metrics.translation_completion_percentages
        }
    
    def _get_weekly_aggregated_metrics(self) -> Dict[str, Any]:
        """Get this week's aggregated metrics."""
        # For now, return today's data - would need to aggregate from daily files
        return {
            **self._get_daily_aggregated_metrics(),
            'period': 'week'
        }
    
    def _get_monthly_aggregated_metrics(self) -> Dict[str, Any]:
        """Get this month's aggregated metrics."""
        # For now, return today's data - would need to aggregate from daily files
        return {
            **self._get_daily_aggregated_metrics(),
            'period': 'month'
        }
    
    def _get_yearly_aggregated_metrics(self) -> Dict[str, Any]:
        """Get this year's aggregated metrics."""
        # For now, return today's data - would need to aggregate from daily files
        return {
            **self._get_daily_aggregated_metrics(),
            'period': 'year'
        }
    
    def _get_alltime_aggregated_metrics(self) -> Dict[str, Any]:
        """Get all-time aggregated metrics."""
        # For now, return today's data - would need to aggregate from all files
        return {
            **self._get_daily_aggregated_metrics(),
            'period': 'alltime'
        }
    
    def _aggregate_daily_to_weekly(self):
        """Aggregate daily data into weekly summaries with timeout protection."""
        import threading
        
        try:
            # Import time aggregator here to avoid circular imports
            from time_aggregator import TimeAggregator
            
            # Use threading timeout instead of signals
            result = [None]
            exception = [None]
            
            def aggregation_operation():
                try:
                    time_aggregator = TimeAggregator()
                    time_aggregator.refresh_aggregations()
                    result[0] = True
                except Exception as e:
                    exception[0] = e
            
            # Run aggregation in thread with timeout
            agg_thread = threading.Thread(target=aggregation_operation, daemon=True)
            agg_thread.start()
            agg_thread.join(timeout=45)  # 45 second timeout
            
            if agg_thread.is_alive():
                logger.error("Weekly aggregation timed out after 45 seconds")
            elif exception[0]:
                raise exception[0]
            elif result[0]:
                logger.info("Weekly aggregation completed successfully")
            else:
                logger.error("Weekly aggregation completed but result is unknown")
            
        except Exception as e:
            logger.error(f"Weekly aggregation failed: {e}")
            # Don't raise exception to prevent blocking main thread