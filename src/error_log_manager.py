"""
Daily Error Log Manager - Captures and manages errors with daily reset functionality.
Provides a centralized system for logging errors that can be viewed in the web interface.
"""

import json
import logging
import traceback
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional
import threading
from collections import defaultdict


class DailyErrorLogManager:
    """Manages daily error logs with automatic reset and web interface integration."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.log_file = Path('data/daily_error_log.json')
        self.lock = threading.Lock()
        self.current_date = date.today().isoformat()
        self.error_logs = self._load_error_logs()
        
        # Setup custom log handler to capture errors
        self._setup_error_handler()
        
    def _load_error_logs(self) -> Dict[str, Any]:
        """Load error logs from file, reset if it's a new day."""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                
                # Check if it's a new day and reset if needed
                stored_date = data.get('date', '')
                if stored_date != self.current_date:
                    self.logger.info(f"New day detected ({self.current_date}), resetting error logs")
                    return self._create_new_log_structure()
                
                self.logger.info("Error logs loaded from file")
                return data
            else:
                self.logger.info("Creating new error log file")
                return self._create_new_log_structure()
                
        except Exception as e:
            self.logger.error(f"Error loading error logs: {e}")
            return self._create_new_log_structure()
    
    def _create_new_log_structure(self) -> Dict[str, Any]:
        """Create new error log structure for the current day."""
        return {
            'date': self.current_date,
            'created_at': datetime.now().isoformat(),
            'error_count': 0,
            'errors': [],
            'error_summary': defaultdict(int),
            'services': {
                'verse_manager': {'errors': 0, 'last_error': None},
                'image_generator': {'errors': 0, 'last_error': None},
                'display_manager': {'errors': 0, 'last_error': None},
                'scheduler': {'errors': 0, 'last_error': None},
                'service_manager': {'errors': 0, 'last_error': None},
                'web_interface': {'errors': 0, 'last_error': None},
                'voice_control': {'errors': 0, 'last_error': None},
                'news_service': {'errors': 0, 'last_error': None},
                'weather_service': {'errors': 0, 'last_error': None},
                'other': {'errors': 0, 'last_error': None}
            }
        }
    
    def _save_error_logs(self):
        """Save error logs to file."""
        try:
            self.log_file.parent.mkdir(exist_ok=True)
            with open(self.log_file, 'w') as f:
                json.dump(self.error_logs, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error saving error logs: {e}")
    
    def _setup_error_handler(self):
        """Setup custom logging handler to capture errors."""
        class ErrorCaptureHandler(logging.Handler):
            def __init__(self, error_manager):
                super().__init__(level=logging.ERROR)
                self.error_manager = error_manager
            
            def emit(self, record):
                if record.levelno >= logging.ERROR:
                    self.error_manager._capture_log_error(record)
        
        # Add our custom handler to the root logger
        error_handler = ErrorCaptureHandler(self)
        logging.getLogger().addHandler(error_handler)
    
    def _capture_log_error(self, record):
        """Capture error from logging system with memory optimization."""
        try:
            # Determine service from logger name
            service_name = self._get_service_name(record.name)
            
            error_info = {
                'timestamp': datetime.now().isoformat(),
                'service': service_name,
                'logger': record.name[:50],  # Limit logger name length
                'level': record.levelname,
                'message': record.getMessage()[:200],  # Limit message length
                'function': getattr(record, 'funcName', 'unknown')[:30],  # Limit function name
                'line': getattr(record, 'lineno', 0),
                'filename': getattr(record, 'filename', 'unknown')[:50]  # Limit filename
            }
            
            # Add limited traceback if available
            if record.exc_info:
                traceback_lines = traceback.format_exception(*record.exc_info)
                # Keep only last 5 lines of traceback to save memory
                limited_traceback = traceback_lines[-5:] if len(traceback_lines) > 5 else traceback_lines
                error_info['traceback'] = ''.join(limited_traceback)[:500]  # Limit total traceback size
            
            self.log_error_internal(error_info)
            
        except Exception as e:
            # Don't let error logging cause more errors
            pass
    
    def _get_service_name(self, logger_name: str) -> str:
        """Determine service name from logger name."""
        service_mapping = {
            'verse_manager': 'verse_manager',
            'image_generator': 'image_generator', 
            'display_manager': 'display_manager',
            'scheduler': 'scheduler',
            'service_manager': 'service_manager',
            'web_interface': 'web_interface',
            'voice_control': 'voice_control',
            'news_service': 'news_service',
            'weather_service': 'weather_service'
        }
        
        for key, service in service_mapping.items():
            if key in logger_name.lower():
                return service
        
        return 'other'
    
    def log_error(self, service: str, error_type: str, message: str, 
                  details: Optional[Dict] = None, exception: Optional[Exception] = None):
        """Log an error with full context."""
        try:
            with self.lock:
                # Check if it's a new day
                current_date = date.today().isoformat()
                if current_date != self.current_date:
                    self.current_date = current_date
                    self.error_logs = self._create_new_log_structure()
                    self.logger.info(f"Error logs reset for new day: {current_date}")
                
                error_info = {
                    'timestamp': datetime.now().isoformat(),
                    'service': service,
                    'error_type': error_type,
                    'message': message,
                    'details': details or {}
                }
                
                # Add limited exception info if provided
                if exception:
                    error_info['exception'] = {
                        'type': type(exception).__name__[:50],  # Limit exception type length
                        'args': str(exception.args)[:150],  # Limit args length
                        'traceback': traceback.format_exc()[:400]  # Limit traceback length
                    }
                
                self.log_error_internal(error_info)
                
        except Exception as e:
            # Fallback logging to prevent error logging from breaking
            self.logger.error(f"Failed to log error: {e}")
    
    def log_error_internal(self, error_info: Dict):
        """Internal method to add error to logs."""
        try:
            # Add to main error list
            self.error_logs['errors'].append(error_info)
            self.error_logs['error_count'] += 1
            
            # Update service-specific counters
            service = error_info.get('service', 'other')
            if service in self.error_logs['services']:
                self.error_logs['services'][service]['errors'] += 1
                self.error_logs['services'][service]['last_error'] = error_info['timestamp']
            
            # Update error type summary
            error_type = error_info.get('error_type', error_info.get('level', 'Unknown'))
            self.error_logs['error_summary'][error_type] += 1
            
            # Keep only last 25 errors to prevent memory buildup
            if len(self.error_logs['errors']) > 25:
                self.error_logs['errors'] = self.error_logs['errors'][-25:]
            
            # Save to file
            self._save_error_logs()
            
        except Exception as e:
            self.logger.error(f"Failed to save error internally: {e}")
    
    def get_daily_error_summary(self) -> Dict[str, Any]:
        """Get summary of today's errors."""
        with self.lock:
            return {
                'date': self.error_logs['date'],
                'total_errors': self.error_logs['error_count'],
                'error_types': dict(self.error_logs['error_summary']),
                'services': {k: v for k, v in self.error_logs['services'].items() if v['errors'] > 0},
                'recent_errors': self.error_logs['errors'][-10:] if self.error_logs['errors'] else []
            }
    
    def get_all_errors(self) -> List[Dict]:
        """Get all errors for today."""
        with self.lock:
            return self.error_logs['errors'].copy()
    
    def get_service_errors(self, service: str) -> List[Dict]:
        """Get errors for a specific service."""
        with self.lock:
            return [error for error in self.error_logs['errors'] if error.get('service') == service]
    
    def clear_errors(self):
        """Manually clear all errors (useful for testing)."""
        with self.lock:
            self.error_logs = self._create_new_log_structure()
            self._save_error_logs()
            self.logger.info("Error logs manually cleared")
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get detailed error statistics."""
        with self.lock:
            recent_errors = self.error_logs['errors'][-5:] if self.error_logs['errors'] else []
            
            # Calculate error frequency
            error_times = [datetime.fromisoformat(error['timestamp']) for error in self.error_logs['errors']]
            error_frequency = {}
            
            if error_times:
                # Group by hour
                for error_time in error_times:
                    hour_key = error_time.strftime('%H:00')
                    error_frequency[hour_key] = error_frequency.get(hour_key, 0) + 1
            
            return {
                'total_errors': self.error_logs['error_count'],
                'services_with_errors': len([s for s in self.error_logs['services'].values() if s['errors'] > 0]),
                'most_problematic_service': max(
                    self.error_logs['services'].items(), 
                    key=lambda x: x[1]['errors']
                )[0] if any(s['errors'] > 0 for s in self.error_logs['services'].values()) else 'None',
                'error_frequency_by_hour': error_frequency,
                'recent_errors': recent_errors,
                'error_types': dict(self.error_logs['error_summary'])
            }


# Global instance
error_log_manager = DailyErrorLogManager()