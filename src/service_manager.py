"""
Main service manager for the Bible Clock application.
"""

import os
import time
import logging
import schedule
import threading
import psutil
from datetime import datetime, timedelta
from typing import Optional

from error_handler import error_handler
from config_validator import ConfigValidator
from scheduler import AdvancedScheduler
from performance_monitor import PerformanceMonitor
from error_log_manager import error_log_manager
from conversation_manager import ConversationManager
from bible_clock_metrics import BibleClockMetrics
from display_schedule_manager import DisplayScheduleManager

class ServiceManager:
    def __init__(self, verse_manager, image_generator, display_manager, voice_control=None, web_interface=None):
        self.verse_manager = verse_manager
        self.image_generator = image_generator
        self.display_manager = display_manager
        self.voice_control = voice_control
        self.web_interface = web_interface
        
        # Set service_manager reference for metrics tracking
        if self.voice_control:
            self.voice_control.service_manager = self
        
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.last_update = None
        self.error_count = 0
        self.max_errors = 10
        
        # Health monitoring settings
        self.memory_threshold = int(os.getenv('MEMORY_THRESHOLD', '80'))
        self.gc_interval = int(os.getenv('GC_INTERVAL', '300'))
        
        # Initialize new components
        self.config_validator = ConfigValidator()
        self.scheduler = AdvancedScheduler()
        self.performance_monitor = PerformanceMonitor()
        self.conversation_manager = ConversationManager()
        self.bible_metrics = BibleClockMetrics()
        
        # Initialize display schedule manager
        self.display_schedule_manager = DisplayScheduleManager()
        self.display_schedule_manager.set_display_callbacks(
            self._scheduled_display_on,
            self._scheduled_display_off
        )
        
        # Track system startup
        self.bible_metrics.track_hardware_event('system_start')
        
        # Validate configuration on startup
        if not self.config_validator.validate_all():
            report = self.config_validator.get_report()
            for error in report['errors']:
                self.logger.error(f"Configuration error: {error}") 
            for warning in report['warnings']:
                self.logger.warning(f"Configuration warning: {warning}")
            if report['errors']:  # Only fail on errors, not warnings
                raise RuntimeError("Configuration validation failed")
        
        # Set up display manager callback for proper cleanup
        self.display_manager.set_restore_callback(self._restore_normal_display)
        
        # Schedule verse updates
        self._schedule_updates()
    
    def _schedule_updates(self):
        """Schedule regular verse updates using advanced scheduler."""
        # Use advanced scheduler for verse updates
        self.scheduler.schedule_verse_updates(self._update_verse)
        
        # Schedule background cycling
        self.scheduler.schedule_background_cycling(self._cycle_background, interval_hours=4)
        
        # Schedule maintenance tasks
        self.scheduler.schedule_maintenance(self._daily_maintenance)
        
        # Schedule performance monitoring
        self.scheduler.schedule_custom('health_check', 'every_5_minutes', self._health_check)
        self.scheduler.schedule_custom('garbage_collect', f'every_{self.gc_interval//60}_minutes', self._garbage_collect)
        self.scheduler.schedule_custom('force_refresh', 'hourly', self._force_refresh)
        
        # Add failsafe verse update check every 30 seconds
        self.scheduler.schedule_custom('verse_update_failsafe', 'every_30_seconds', self._failsafe_verse_update)
        
        # Schedule frequent pagination checks for book summaries
        self.scheduler.schedule_custom('pagination_check', 'every_10_seconds', self._check_pagination)
        
        # Schedule weather page rotation checks (30-second page flips)
        self.scheduler.schedule_custom('weather_page_rotation', 'every_15_seconds', self._check_weather_page_rotation)
        
        # Schedule metrics aggregation refresh
        self.scheduler.schedule_custom('metrics_aggregation', 'every_5_minutes', self._refresh_metrics_aggregation)
        
        self.logger.info("Advanced update schedule configured")
    
    def run(self):
        """Main service loop."""
        self.running = True
        
        # Start performance monitoring
        self.performance_monitor.start_monitoring()
        
        # Start advanced scheduler
        self.scheduler.start()
        
        # Start display schedule manager
        self.display_schedule_manager.start_scheduler()
        
        # Start simple update thread as backup to complex scheduler
        self._start_simple_updater()
        
        # Start web interface FIRST (before voice control blocks)
        if self.web_interface:
            self._start_web_interface()
        
        # Start voice control if available (runs in blocking mode)
        if self.voice_control:
            # Mark voice control as initialized to enable visual feedback
            if hasattr(self.voice_control, 'mark_initialized'):
                self.voice_control.mark_initialized()
            self.voice_control.run_main_loop()
        elif os.getenv('ENABLE_VOICE', 'false').lower() == 'true':
            # Try to initialize voice control if enabled but not provided
            try:
                from voice_control import BibleClockVoiceControl
                self.voice_control = BibleClockVoiceControl(
                    self.verse_manager, self.image_generator, self.display_manager
                )
                # Set service_manager reference for metrics tracking
                self.voice_control.service_manager = self
                if hasattr(self.voice_control, 'enabled') and self.voice_control.enabled:
                    # Mark voice control as initialized to enable visual feedback
                    if hasattr(self.voice_control, 'mark_initialized'):
                        self.voice_control.mark_initialized()
                    self.voice_control.run_main_loop()
                    self.logger.info("Voice control auto-initialized")
            except Exception as e:
                self.logger.error(f"Voice control auto-initialization failed: {e}")
        
        # Initial verse display
        self._update_verse()
        
        self.logger.info("Bible Clock service started")
        
        try:
            while self.running:
                # The advanced scheduler runs in its own thread
                # Just keep the main thread alive
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Service interrupted by user")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the service."""
        self.running = False
        
        # Stop all components
        self.scheduler.stop()
        self.performance_monitor.stop_monitoring()
        
        # Stop display schedule manager
        if hasattr(self, 'display_schedule_manager'):
            self.display_schedule_manager.stop_scheduler()
        
        if self.voice_control:
            self.voice_control.stop_listening()
        
        if self.web_interface:
            self._stop_web_interface()
        
        # Track system shutdown
        self.bible_metrics.track_hardware_event('system_stop')
        
        self.logger.info("Bible Clock service stopped")
    
    @error_handler.with_retry(max_retries=2)
    def _update_verse(self):
        """Update the displayed verse at precise minute boundaries."""
        # Check if display is locked for AI responses
        if hasattr(self.display_manager, 'is_display_locked') and self.display_manager.is_display_locked():
            self.logger.debug("Skipping verse update - display locked for AI response")
            return
        
        # Check if display should be on according to schedule
        if hasattr(self, 'display_schedule_manager') and self.display_schedule_manager:
            if not self.display_schedule_manager.is_display_scheduled_on():
                self.logger.debug("Skipping verse update - display scheduled to be off")
                # Clear display if it's not already clear
                if not hasattr(self, '_display_cleared_by_schedule') or not self._display_cleared_by_schedule:
                    self.display_manager.clear_display()
                    self._display_cleared_by_schedule = True
                    self.logger.info("Display cleared due to schedule")
                return
            else:
                # Reset the flag when display should be on
                self._display_cleared_by_schedule = False
            
        now = datetime.now()
        
        # Check if we need frequent updates for book summary pagination
        last_verse_data = getattr(self, '_last_verse_data', None)
        is_summary_mode = last_verse_data and last_verse_data.get('is_summary', False) if last_verse_data else False
        
        # Track last update time more reliably
        if not hasattr(self, '_last_update_time'):
            self._last_update_time = time.time()
        
        # Check if this is weather or news mode
        is_weather_mode = last_verse_data and last_verse_data.get('is_weather_mode', False) if last_verse_data else False
        is_news_mode = last_verse_data and last_verse_data.get('is_news_mode', False) if last_verse_data else False
        
        # Different update rules for different modes
        if is_weather_mode or is_news_mode:
            # Weather/News mode: update every 30 seconds (not just minute boundaries)
            time_since_last_update = time.time() - self._last_update_time
            should_update = time_since_last_update >= 30
        else:
            # Other modes: minute boundary OR pagination
            minute_boundary_update = now.second <= 2
            time_since_last_update = time.time() - self._last_update_time
            summary_pagination_update = is_summary_mode and time_since_last_update >= 15
            should_update = minute_boundary_update or summary_pagination_update
        
        if should_update:
            if is_weather_mode:
                self.logger.info(f"Weather mode - triggering 30-second update (last update: {time_since_last_update:.1f}s ago)")
            elif is_news_mode:
                self.logger.info(f"News mode - triggering 30-second update (last update: {time_since_last_update:.1f}s ago)")
            elif summary_pagination_update:
                self.logger.info(f"Book summary pagination - triggering 15-second update (last update: {time_since_last_update:.1f}s ago)")
            with self.performance_monitor.time_operation('verse_update'):
                # Get current verse
                verse_data = self.verse_manager.get_current_verse()
                
                # Store verse data for next iteration's summary mode check
                self._last_verse_data = verse_data
                
                # Generate image
                image = self.image_generator.create_verse_image(verse_data)
                
                # Check if background changed and force refresh only for background changes
                background_changed = self.image_generator.background_changed_since_last_render()
                if background_changed:
                    self.logger.info("Background changed - forcing full refresh")
                
                # Check if parallel mode changed (to prevent artifacts)
                current_parallel_mode = verse_data.get('parallel_mode', False)
                # Initialize last_parallel_mode on first run to avoid false positive changes
                if not hasattr(self, 'last_parallel_mode'):
                    self.last_parallel_mode = current_parallel_mode
                    parallel_mode_changed = False  # Don't trigger on first initialization
                    self.logger.debug(f"Initialized parallel mode tracking: {current_parallel_mode}")
                else:
                    parallel_mode_changed = self.last_parallel_mode != current_parallel_mode
                    
                if parallel_mode_changed:
                    self.logger.info(f"Parallel mode changed from {self.last_parallel_mode} to {current_parallel_mode} - forcing full refresh to prevent artifacts")
                    self.last_parallel_mode = current_parallel_mode
                
                # Display image with smart refresh logic
                # Force full refresh for parallel mode to prevent artifacts
                # Use partial refresh for devotional mode to reduce jarring updates
                # Use optimized refresh for date mode to prevent cycling artifacts
                is_devotional_mode = verse_data.get('is_devotional', False)
                is_date_mode = verse_data.get('is_date_event', False)
                is_summary_mode = verse_data.get('is_summary', False)
                
                if is_devotional_mode:
                    # For devotional mode, refresh periodically to update time display but not content
                    time_since_last_refresh = time.time() - self.display_manager.last_full_refresh
                    should_refresh_for_time = time_since_last_refresh >= 60  # Refresh every minute for time display
                    force_refresh = background_changed or parallel_mode_changed or should_refresh_for_time
                elif is_date_mode:
                    # For date mode, force refresh on every cycle but preserve borders to reduce jarring
                    # Date mode cycles content every minute, so we need clean refreshes
                    force_refresh = True  # Always force refresh for date mode cycling
                    self.logger.debug("Date mode cycling - forcing border-preserving refresh to prevent artifacts")
                elif is_summary_mode:
                    # For book summaries, check if we need frequent refresh for pagination
                    time_since_last_refresh = time.time() - self.display_manager.last_full_refresh
                    # Refresh every 15 seconds for book summary pagination (matches page rotation)
                    should_refresh_by_interval = time_since_last_refresh >= 15
                    force_refresh = background_changed or parallel_mode_changed or should_refresh_by_interval
                    if should_refresh_by_interval:
                        self.logger.debug("Book summary page rotation - refreshing display")
                else:
                    # For parallel mode, only force refresh based on display manager's interval, not every minute
                    if current_parallel_mode:
                        # Check if it's time for a scheduled refresh based on display manager interval
                        time_since_last_refresh = time.time() - self.display_manager.last_full_refresh
                        refresh_interval_minutes = self.display_manager.force_refresh_interval
                        should_refresh_by_interval = time_since_last_refresh >= (refresh_interval_minutes * 60)
                        force_refresh = background_changed or parallel_mode_changed or should_refresh_by_interval
                    else:
                        # For non-parallel modes, only refresh on changes
                        force_refresh = background_changed or parallel_mode_changed
                
                # Use border-preserving refresh for date mode to reduce visual jarring
                preserve_border = is_date_mode and force_refresh
                self.display_manager.display_image(image, force_refresh=force_refresh, preserve_border=preserve_border)
                
                # Update tracking
                self.last_update = datetime.now()
                self._last_update_time = time.time()  # Track for pagination timing
                self.error_count = 0
                
                # Track verse display in real-time metrics system
                try:
                    self.bible_metrics.track_verse_displayed(verse_data)
                except Exception as e:
                    self.logger.debug(f"Failed to track verse metrics: {e}")  # Debug level to avoid spam
                
                self._last_verse_update_time = time.time()  # Track for failsafe
                self.logger.info(f"Verse updated: {verse_data['reference']} at {now.strftime('%H:%M:%S')}")
        else:
            self.logger.debug(f"Skipping verse update at {now.strftime('%H:%M:%S')} - not at minute boundary")
    
    def _health_check(self):
        """Perform system health checks."""
        try:
            # Check memory usage
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > self.memory_threshold:
                self.logger.warning(f"High memory usage: {memory_percent}%")
                self.bible_metrics.track_hardware_event('low_memory', f"Memory usage at {memory_percent:.1f}%")
            
            # Check last update time
            if self.last_update:
                time_since_update = datetime.now() - self.last_update
                if time_since_update > timedelta(minutes=5):
                    self.logger.warning(f"No updates for {time_since_update}")
            
            # Check error rate
            if self.error_count > 5:
                self.logger.warning(f"High error count: {self.error_count}")
            
            # Check disk space
            disk_usage = psutil.disk_usage('/')
            disk_percent = (disk_usage.used / disk_usage.total) * 100
            if disk_percent > 90:
                self.logger.warning(f"Low disk space: {disk_percent:.1f}% used")
            
            self.logger.debug("Health check completed")
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            error_log_manager.log_error('service_manager', 'health_check_failure', 
                                      f"Health check failed: {e}", exception=e)
    
    def _garbage_collect(self):
        """Force garbage collection to free memory."""
        try:
            import gc
            before = psutil.virtual_memory().percent
            gc.collect()
            after = psutil.virtual_memory().percent
            
            if before - after > 1:  # Only log if significant reduction
                self.logger.info(f"Garbage collection: {before:.1f}% -> {after:.1f}% memory")
            
        except Exception as e:
            self.logger.error(f"Garbage collection failed: {e}")
            error_log_manager.log_error('service_manager', 'garbage_collection_failure', 
                                      f"Garbage collection failed: {e}", exception=e)
    
    def _check_pagination(self):
        """Check if we need to update display for pagination (book summaries, devotionals)."""
        try:
            # Only run pagination check if we have recent verse data
            last_verse_data = getattr(self, '_last_verse_data', None)
            if not last_verse_data:
                return
            
            # Check if current display needs pagination updates
            needs_pagination = (
                last_verse_data.get('is_summary', False) or 
                last_verse_data.get('is_devotional', False) or
                last_verse_data.get('total_pages', 1) > 1
            )
            
            if not needs_pagination:
                return
                
            # Check if enough time has passed since last update
            if not hasattr(self, '_last_update_time'):
                return
                
            time_since_last_update = time.time() - self._last_update_time
            
            # Trigger update every 15 seconds for multi-page content
            if time_since_last_update >= 15:
                self.logger.info(f"Pagination update triggered - {time_since_last_update:.1f}s since last update")
                
                # Force a display update for pagination
                verse_data = self.verse_manager.get_current_verse()
                self._last_verse_data = verse_data
                
                image = self.image_generator.create_verse_image(verse_data)
                self.display_manager.display_image(image, force_refresh=False)
                
                # Update timing
                self._last_update_time = time.time()
                
                self.logger.info(f"Pagination update completed: {verse_data.get('reference', 'Unknown')} page {verse_data.get('current_page', 1)} of {verse_data.get('total_pages', 1)}")
                
        except Exception as e:
            self.logger.error(f"Pagination check failed: {e}")
            error_log_manager.log_error('service_manager', 'pagination_check_failure', 
                                      f"Pagination check failed: {e}", exception=e)
    
    def _check_weather_page_rotation(self):
        """Check if weather display needs page rotation update."""
        try:
            # Only run for weather mode
            last_verse_data = getattr(self, '_last_verse_data', None)
            if not last_verse_data or not last_verse_data.get('is_weather_mode'):
                return
                
            # Check if enough time has passed since last update (at least 15 seconds)
            if not hasattr(self, '_last_update_time'):
                return
                
            time_since_last_update = time.time() - self._last_update_time
            
            # Update every 15 seconds to ensure page flips are caught
            if time_since_last_update >= 15:
                self.logger.info(f"Weather page rotation check - updating display")
                
                # Force a display update for page rotation
                verse_data = self.verse_manager.get_current_verse()
                self._last_verse_data = verse_data
                
                image = self.image_generator.create_verse_image(verse_data)
                self.display_manager.display_image(image, force_refresh=False)
                
                # Update timing
                self._last_update_time = time.time()
                
                self.logger.info(f"Weather page rotation update completed")
                
        except Exception as e:
            self.logger.error(f"Weather page rotation check failed: {e}")
    
    def _force_refresh(self):
        """Force a full display refresh to prevent ghosting and check for weather updates."""
        try:
            self.logger.info("Performing scheduled full refresh")
            
            # Check if current display is weather mode and if data needs refresh
            verse_data = self.verse_manager.get_current_verse()
            needs_weather_refresh = False
            
            if verse_data and verse_data.get('is_weather_mode'):
                try:
                    from weather_service import weather_service
                    needs_weather_refresh = weather_service.should_refresh_weather_data()
                    if needs_weather_refresh:
                        self.logger.info("Weather data refresh triggered during scheduled refresh")
                except Exception as e:
                    self.logger.error(f"Error checking weather refresh status: {e}")
            
            # Generate new image (weather mode will automatically refresh data if needed)
            image = self.image_generator.create_verse_image(verse_data)
            self.display_manager.display_image(image, force_refresh=True)
            
            if needs_weather_refresh:
                self.logger.info("Weather display refreshed with updated data")
                
        except Exception as e:
            self.logger.error(f"Force refresh failed: {e}")
            error_log_manager.log_error('service_manager', 'force_refresh_failure', 
                                      f"Force refresh failed: {e}", exception=e)
    
    def _restore_normal_display(self):
        """Restore normal Bible verse display (called by display manager cleanup)."""
        try:
            self.logger.info("Restoring normal display after transient message")
            verse_data = self.verse_manager.get_current_verse()
            image = self.image_generator.create_verse_image(verse_data)
            self.display_manager.display_image(image, force_refresh=True)
        except Exception as e:
            self.logger.error(f"Failed to restore normal display: {e}")
            # Fallback to clearing display
            try:
                self.display_manager.clear_display()
            except Exception as e2:
                self.logger.error(f"Failed to clear display as fallback: {e2}")
    
    def _cycle_background(self):
        """Automatically cycle background image."""
        try:
            self.image_generator.cycle_background()
            self.logger.info("Background automatically cycled")
        except Exception as e:
            self.logger.error(f"Background cycling failed: {e}")
    
    def _daily_maintenance(self):
        """Perform daily maintenance tasks."""
        try:
            self.logger.info("Starting daily maintenance")
            
            # Force garbage collection
            self._garbage_collect()
            
            # Clear old log entries if needed
            # Add any other maintenance tasks here
            
            self.logger.info("Daily maintenance completed")
        except Exception as e:
            self.logger.error(f"Daily maintenance failed: {e}")
    
    def _update_aggregated_metrics(self):
        """Update aggregated metrics from verse manager statistics."""
        try:
            # Get current verse manager statistics
            vm_stats = self.verse_manager.statistics
            now = datetime.now()
            today_str = now.strftime('%Y-%m-%d')
            
            # Create aggregated metrics entry using real verse statistics
            from conversation_manager import AggregatedMetrics
            
            # Get books accessed as dict with counts (instead of just set)
            books_accessed = {}
            if hasattr(self.verse_manager, 'get_book_chapter_breakdown'):
                book_breakdown = self.verse_manager.get_book_chapter_breakdown()
                for book_data in book_breakdown.get('book_totals', []):
                    books_accessed[book_data['book']] = book_data['total_verses']
            else:
                # Fallback: convert set to dict with count 1
                for book in vm_stats.get('books_accessed', []):
                    books_accessed[book] = books_accessed.get(book, 0) + 1
            
            # Create daily aggregated metrics
            aggregated_metrics = AggregatedMetrics(
                date=today_str,
                total_conversations=vm_stats.get('verses_today', 0),  # Total verses displayed today
                categories={'verses_displayed': vm_stats.get('verses_today', 0)},  # Store as verses_displayed category
                keywords={},  # We don't have keyword tracking in verse manager yet
                avg_response_time=0.1,  # Placeholder for verse generation time
                success_rate=100.0,  # Assume all verse displays are successful
                hourly_distribution=self._get_hourly_distribution(vm_stats)
            )
            
            # Save to conversation manager's aggregated data
            self.conversation_manager.aggregated_data[today_str] = aggregated_metrics
            
            # Also update the aggregated_metrics.json file directly
            self._save_daily_metrics(today_str, aggregated_metrics, books_accessed, vm_stats.get('translation_usage', {}))
            
        except Exception as e:
            self.logger.debug(f"Failed to update aggregated metrics: {e}")
    
    def _get_hourly_distribution(self, vm_stats):
        """Extract hourly distribution from verse manager statistics."""
        # For now, just put current hour with count of verses today
        current_hour = datetime.now().hour
        verses_today = vm_stats.get('verses_today', 0)
        if verses_today > 0:
            return {str(current_hour): verses_today}
        return {}
    
    def _calculate_mode_usage_hours(self, mode_usage_counts):
        """Convert mode usage counts (minutes/verses) to hours."""
        mode_hours = {}
        for mode, count in mode_usage_counts.items():
            # Assume each verse display takes 1 minute, so count = minutes
            # Convert to hours (rounded to 1 decimal place)
            hours = round(count / 60.0, 1)
            mode_hours[mode] = hours
        return mode_hours
    
    def _save_daily_metrics(self, date_str, aggregated_metrics, books_accessed, translation_usage):
        """Save daily metrics to aggregated_metrics.json file."""
        try:
            import json
            from pathlib import Path
            
            metrics_file = Path('data/aggregated_metrics.json')
            
            # Load existing data
            if metrics_file.exists():
                with open(metrics_file, 'r') as f:
                    all_data = json.load(f)
            else:
                all_data = {}
            
            # Get the current mode usage in hours (not verse count)
            vm_stats = self.verse_manager.statistics
            mode_usage_hours = self._calculate_mode_usage_hours(vm_stats.get('mode_usage', {}))
            
            # Create the entry
            all_data[date_str] = {
                'date': date_str,
                'total_conversations': aggregated_metrics.total_conversations,  # This is actually verses displayed
                'categories': {'verses_displayed': aggregated_metrics.total_conversations},
                'keywords': aggregated_metrics.keywords,
                'avg_response_time': aggregated_metrics.avg_response_time,
                'success_rate': aggregated_metrics.success_rate,
                'hourly_distribution': aggregated_metrics.hourly_distribution,
                'translation_usage': translation_usage,
                'bible_books_accessed': books_accessed,
                'mode_usage_hours': mode_usage_hours  # Store hours separately
            }
            
            # Save back to file
            with open(metrics_file, 'w') as f:
                json.dump(all_data, f, indent=2)
                
        except Exception as e:
            self.logger.debug(f"Failed to save daily metrics: {e}")

    def _refresh_metrics_aggregation(self):
        """Refresh metrics aggregation data from daily conversation logs."""
        try:
            # Import time aggregator here to avoid circular imports
            from time_aggregator import TimeAggregator
            
            # Create time aggregator instance and refresh data
            time_aggregator = TimeAggregator()
            time_aggregator.refresh_aggregations()
            
            self.logger.debug("Metrics aggregation refreshed successfully")
            
        except Exception as e:
            self.logger.error(f"Metrics aggregation refresh failed: {e}")
            error_log_manager.log_error('service_manager', 'metrics_aggregation_failure',
                                      f"Metrics aggregation refresh failed: {e}", exception=e)
    
    def _start_web_interface(self):
        """Start the web interface in a separate thread."""
        try:
            import threading
            from web_interface.app import create_app
            
            # Create Flask app with all components
            app = create_app(
                verse_manager=self.verse_manager,
                image_generator=self.image_generator,
                display_manager=self.display_manager,
                service_manager=self,
                performance_monitor=self.performance_monitor
            )
            
            # Get web interface configuration
            display_host = os.getenv('WEB_HOST', 'bible-clock')
            bind_host = '0.0.0.0'  # Flask must bind to IP, not hostname
            port = int(os.getenv('WEB_PORT', '7777'))
            debug = os.getenv('WEB_DEBUG', 'false').lower() == 'true'
            
            # Start Flask app in a separate thread
            def run_web_interface():
                app.run(host=bind_host, port=port, debug=debug, use_reloader=False)
            
            self.web_thread = threading.Thread(target=run_web_interface, daemon=True)
            self.web_thread.start()
            
            self.logger.info(f"Web interface started on http://{display_host}:{port}")
            
        except Exception as e:
            self.logger.error(f"Failed to start web interface: {e}")
    
    def _stop_web_interface(self):
        """Stop the web interface."""
        try:
            # Flask server will stop when the main thread exits
            # since we're using daemon threads
            if hasattr(self, 'web_thread') and self.web_thread.is_alive():
                self.logger.info("Web interface stopping...")
        except Exception as e:
            self.logger.error(f"Error stopping web interface: {e}")
    
    def _scheduled_display_on(self):
        """Callback when display is turned on by schedule."""
        try:
            self.logger.info("Display turned ON by schedule - resuming normal operation")
            # Reset the cleared flag and force an immediate verse update
            self._display_cleared_by_schedule = False
            self._update_verse()
            # Track the event
            self.bible_metrics.track_hardware_event('scheduled_display_on', 'Display resumed by schedule')
        except Exception as e:
            self.logger.error(f"Failed to handle scheduled display on: {e}")
    
    def _scheduled_display_off(self):
        """Callback when display is turned off by schedule."""
        try:
            self.logger.info("Display turned OFF by schedule - clearing display")
            # Set the flag and clear the display
            self._display_cleared_by_schedule = True
            self.display_manager.clear_display()
            # Track the event
            self.bible_metrics.track_hardware_event('scheduled_display_off', 'Display cleared by schedule')
        except Exception as e:
            self.logger.error(f"Failed to handle scheduled display off: {e}")
    
    def _failsafe_verse_update(self):
        """Failsafe method to ensure verse updates happen even if scheduler fails."""
        try:
            now = datetime.now()
            
            # Skip if display is scheduled to be off
            if hasattr(self, 'display_schedule_manager') and self.display_schedule_manager:
                if not self.display_schedule_manager.is_display_scheduled_on():
                    return
            
            # Check if it's been too long since last update
            if not hasattr(self, '_last_verse_update_time'):
                self._last_verse_update_time = time.time()
                self._update_verse()  # Force first update
                return
            
            time_since_last_update = time.time() - self._last_verse_update_time
            
            # Force update if it's been more than 90 seconds (should be ~60 seconds normally)
            # Or if we're at a minute boundary and it's been more than 30 seconds
            minute_boundary = now.second <= 5
            too_long_since_update = time_since_last_update > 90
            minute_boundary_overdue = minute_boundary and time_since_last_update > 30
            
            if too_long_since_update or minute_boundary_overdue:
                self.logger.info(f"Failsafe triggering verse update (last update: {time_since_last_update:.1f}s ago)")
                self._last_verse_update_time = time.time()
                self._update_verse()
                
        except Exception as e:
            self.logger.error(f"Failsafe verse update failed: {e}")
    
    def _start_simple_updater(self):
        """Start a simple backup updater thread."""
        def simple_update_loop():
            import time
            last_update_minute = -1
            
            while self.running:
                try:
                    now = datetime.now()
                    current_minute = now.minute
                    
                    # Update at the start of each new minute
                    if current_minute != last_update_minute and now.second <= 10:
                        # Check if display should be on
                        should_update = True
                        if hasattr(self, 'display_schedule_manager') and self.display_schedule_manager:
                            should_update = self.display_schedule_manager.is_display_scheduled_on()
                        
                        if should_update:
                            self.logger.info(f"Simple updater triggering verse update at {now.strftime('%H:%M:%S')}")
                            self._update_verse()
                        
                        last_update_minute = current_minute
                    
                    time.sleep(5)  # Check every 5 seconds
                    
                except Exception as e:
                    self.logger.error(f"Simple updater error: {e}")
                    time.sleep(10)
        
        self.simple_updater_thread = threading.Thread(target=simple_update_loop, daemon=True)
        self.simple_updater_thread.start()
        self.logger.info("Simple backup updater started")
    
    def get_status(self) -> dict:
        """Get current service status."""
        status = {
            'running': self.running,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'error_count': self.error_count,
            'memory_usage': psutil.virtual_memory().percent,
            'display_info': self.display_manager.get_display_info(),
            'background_info': self.image_generator.get_current_background_info(),
            'scheduler_jobs': self.scheduler.get_job_status(),
            'performance_summary': self.performance_monitor.get_performance_summary()
        }
        
        # Add configuration validation report
        config_report = self.config_validator.get_report()
        status['configuration'] = config_report
        
        # Add display schedule status if available
        if hasattr(self, 'display_schedule_manager'):
            schedule_info = self.display_schedule_manager.get_schedule()
            status['display_schedule'] = {
                'enabled': True,
                'current_status': schedule_info.get('current_status', {}),
                'next_event': self.display_schedule_manager.get_next_schedule_event()
            }
        
        return status