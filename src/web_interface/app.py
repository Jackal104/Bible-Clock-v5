"""
Enhanced web interface for Bible Clock with full configuration and statistics.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, send_file, current_app, redirect
from pathlib import Path
import psutil
from src.conversation_manager import ConversationManager
from src.error_log_manager import error_log_manager
from src.time_aggregator import TimeAggregator

def create_app(verse_manager, image_generator, display_manager, service_manager, performance_monitor):
    """Create enhanced Flask application."""
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.logger.setLevel(logging.INFO)
    
    # Disable template caching for development
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    
    # Store component references
    app.verse_manager = verse_manager
    app.image_generator = image_generator
    app.display_manager = display_manager
    app.service_manager = service_manager
    app.performance_monitor = performance_monitor
    app.conversation_manager = ConversationManager()
    app.time_aggregator = TimeAggregator()
    app.bible_metrics = service_manager.bible_metrics  # Use the same instance
    
    # Initialize display mode manager
    try:
        # Try different import paths
        try:
            from display_mode_manager import DisplayModeManager
        except ImportError:
            from src.display_mode_manager import DisplayModeManager
        
        app.display_mode_manager = DisplayModeManager()
        app.logger.info("DisplayModeManager initialized successfully")
    except Exception as e:
        app.logger.warning(f"Could not initialize DisplayModeManager: {e}")
        app.display_mode_manager = None
        
    # Initialize display schedule manager
    try:
        # Try different import paths
        try:
            from display_schedule_manager import DisplayScheduleManager
        except ImportError:
            from src.display_schedule_manager import DisplayScheduleManager
        
        app.display_schedule_manager = DisplayScheduleManager()
        # Set up callbacks for display control
        app.display_schedule_manager.set_display_callbacks(
            lambda: _turn_display_on(app),
            lambda: _turn_display_off(app)
        )
        app.logger.info("DisplayScheduleManager initialized successfully")
    except Exception as e:
        app.logger.warning(f"Could not initialize DisplayScheduleManager: {e}")
        app.display_schedule_manager = None
    
    # Activity tracking for recent activity log
    app.recent_activities = []
    
    # Add initial activity
    def _track_activity(action: str, details: str = None):
        """Track activity for recent activity log."""
        try:
            activity = {
                'timestamp': datetime.now().isoformat(),
                'action': action,
                'details': details or '',
                'type': 'system'
            }
            
            # Use app directly when outside request context, current_app when in request context
            try:
                from flask import has_request_context
                if has_request_context():
                    current_app.recent_activities.append(activity)
                    # Keep only last 100 activities to prevent memory growth
                    if len(current_app.recent_activities) > 100:
                        current_app.recent_activities = current_app.recent_activities[-100:]
                else:
                    app.recent_activities.append(activity)
                    # Keep only last 100 activities to prevent memory growth
                    if len(app.recent_activities) > 100:
                        app.recent_activities = app.recent_activities[-100:]
            except:
                # Fallback to app reference
                app.recent_activities.append(activity)
                if len(app.recent_activities) > 100:
                    app.recent_activities = app.recent_activities[-100:]
                
        except Exception as e:
            try:
                from flask import has_request_context
                if has_request_context():
                    current_app.logger.error(f"Activity tracking error: {e}")
                else:
                    app.logger.error(f"Activity tracking error: {e}")
            except:
                app.logger.error(f"Activity tracking error: {e}")
    
    # Initial activity and test activities
    _track_activity("Web interface started", "Bible Clock web interface initialized")
    _track_activity("System startup", "Bible Clock system started successfully")
    _track_activity("Display initialized", "E-ink display ready for verse display")
    
    def _turn_display_on(app_context):
        """Turn display on - callback for display schedule manager."""
        try:
            app_context.logger.info("Display turned ON via schedule - resuming verse updates")
            # Force an immediate verse update to show the display is active
            if hasattr(app_context.service_manager, '_update_verse'):
                app_context.service_manager._update_verse()
            _track_activity("Display ON", "Display turned on by schedule - services resumed")
        except Exception as e:
            app_context.logger.error(f"Failed to turn display on: {e}")
    
    def _turn_display_off(app_context):
        """Turn display off - callback for display schedule manager."""
        try:
            # Clear the display and keep it blank - this stops regular updates
            app_context.display_manager.clear_display()
            app_context.logger.info("Display turned OFF via schedule - display cleared")
            _track_activity("Display OFF", "Display turned off by schedule - display cleared")
        except Exception as e:
            app_context.logger.error(f"Failed to turn display off: {e}")
    
    def _is_mobile_device(request):
        """Detect if the request is from a mobile device."""
        user_agent = request.headers.get('User-Agent', '').lower()
        mobile_keywords = [
            'mobile', 'android', 'iphone', 'ipad', 'ipod', 
            'windows phone', 'blackberry', 'webos', 'opera mini',
            'phone', 'tablet'
        ]
        return any(keyword in user_agent for keyword in mobile_keywords)
    
    @app.route('/')
    def index():
        """Main dashboard with mobile detection."""
        # Check for force desktop parameter
        if request.args.get('force_desktop') == '1':
            return render_template('dashboard.html')
        
        # Check if mobile device
        if _is_mobile_device(request):
            return render_template('mobile/dashboard.html')
        else:
            return render_template('dashboard.html')
    
    @app.route('/settings')
    def settings():
        """Settings page with mobile detection."""
        # Check for force desktop parameter
        if request.args.get('force_desktop') == '1':
            return render_template('settings.html')
        
        # Check if mobile device
        if _is_mobile_device(request):
            return render_template('mobile/settings.html')
        else:
            return render_template('settings.html')
    
    # @app.route('/display-schedule')
    # def display_schedule_page():
    #     """Display schedule configuration page."""
    #     return render_template('display_schedule.html')
    
    @app.route('/backgrounds')
    def backgrounds():
        """Redirect to display modes page - backgrounds functionality merged."""
        return redirect('/display-modes')
    
    @app.route('/display-modes')
    def display_modes():
        """Display mode customization page with mobile detection."""
        # Check for force desktop parameter
        if request.args.get('force_desktop') == '1':
            return render_template('settings.html')  # Desktop uses settings page for now
        
        # Check if mobile device
        if _is_mobile_device(request):
            return render_template('mobile/display_modes.html')
        else:
            return render_template('settings.html')  # Desktop uses settings page for now
    
    @app.route('/statistics')
    def statistics():
        """Statistics page with mobile detection."""
        # Check for force desktop parameter
        if request.args.get('force_desktop') == '1':
            return render_template('statistics.html')
        
        # Check if mobile device
        if _is_mobile_device(request):
            return render_template('mobile/statistics.html')
        else:
            return render_template('statistics.html')
    
    @app.route('/voice')
    def voice_control():
        """Voice control page with mobile detection."""
        # Check for force desktop parameter
        if request.args.get('force_desktop') == '1':
            return render_template('voice_control.html')
        
        # Check if mobile device
        if _is_mobile_device(request):
            return render_template('mobile/voice_control.html')
        else:
            return render_template('voice_control.html')
    
    @app.route('/health')
    def health_status():
        """Simple health status page for gift recipient."""
        return render_template('health.html')
    
    # === API Endpoints ===
    
    @app.route('/api/verse', methods=['GET'])
    def get_current_verse():
        """Get the current verse as JSON."""
        try:
            verse_data = current_app.verse_manager.get_current_verse()
            verse_data['timestamp'] = datetime.now().isoformat()
            
            return jsonify({
                'success': True,
                'data': verse_data
            })
        except Exception as e:
            current_app.logger.error(f"API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/status', methods=['GET'])
    def get_status():
        """Get comprehensive system status."""
        try:
            # Check simulation mode from display manager
            simulation_mode = getattr(current_app.display_manager, 'simulation_mode', False)
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'translation': current_app.verse_manager.get_configured_translation(),
                'api_url': current_app.verse_manager.api_url,
                'display_mode': getattr(current_app.verse_manager, 'display_mode', 'time'),
                'parallel_mode': getattr(current_app.verse_manager, 'parallel_mode', False),
                'secondary_translation': current_app.verse_manager.get_configured_secondary_translation(),
                'simulation_mode': simulation_mode,
                'hardware_mode': 'Simulation' if simulation_mode else 'Hardware',
                'current_background': current_app.image_generator.get_current_background_info(),
                'verses_today': _get_accurate_verses_today(),
                'system': {
                    'cpu_percent': psutil.cpu_percent(),
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_percent': psutil.disk_usage('/').percent,
                    'cpu_temperature': _get_cpu_temperature(),
                    'uptime': _get_uptime(),
                    'health_status': _get_system_health_status(),
                    'health_details': _get_health_details()
                }
            }
            
            if current_app.performance_monitor:
                status['performance'] = current_app.performance_monitor.get_performance_summary()
            
            return jsonify({'success': True, 'data': status})
        except Exception as e:
            current_app.logger.error(f"Status API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/storage', methods=['GET'])
    def get_storage_stats():
        """Get hard drive storage statistics."""
        try:
            # Get disk usage for the root filesystem
            disk_usage = psutil.disk_usage('/')
            
            # Calculate percentages
            used_percent = (disk_usage.used / disk_usage.total) * 100
            free_percent = (disk_usage.free / disk_usage.total) * 100
            
            # Convert bytes to GB for readability
            total_gb = disk_usage.total / (1024**3)
            used_gb = disk_usage.used / (1024**3)
            free_gb = disk_usage.free / (1024**3)
            
            # Get translation completion percentages (excluding WEB)
            translation_completion = getattr(current_app.verse_manager, 'translation_completion', {})
            
            # Filter out WEB translation if it exists
            if 'web' in translation_completion:
                del translation_completion['web']
            
            # If no completion data, calculate basic completion based on file existence (excluding WEB)
            if not translation_completion:
                translation_completion = {}
                # Include CEV and all available translations
                for translation in ['kjv', 'amp', 'esv', 'nlt', 'msg', 'nasb', 'ylt', 'cev']:
                    # Handle special case for NASB which uses nasb1995 file
                    file_name = translation
                    if translation == 'nasb':
                        file_name = 'nasb1995'
                    
                    file_path = Path(f'data/translations/bible_{file_name}.json')
                    if file_path.exists():
                        # Better completion calculation based on actual file size
                        size_bytes = file_path.stat().st_size
                        if size_bytes > 3500000:  # > 3.5MB likely complete (adjusted threshold)
                            translation_completion[translation] = 100.0
                        elif size_bytes > 2500000:  # > 2.5MB very high completion
                            translation_completion[translation] = 95.0
                        elif size_bytes > 1500000:  # > 1.5MB high completion  
                            translation_completion[translation] = 85.0
                        elif size_bytes > 800000:  # > 800KB medium completion
                            translation_completion[translation] = 65.0
                        elif size_bytes > 100000:  # > 100KB some completion
                            translation_completion[translation] = 35.0
                        else:
                            translation_completion[translation] = 5.0
                    else:
                        translation_completion[translation] = 0.0
            
            # Calculate Bible storage statistics (excluding WEB)
            total_translations = len(['kjv', 'amp', 'esv', 'nlt', 'msg', 'nasb', 'ylt', 'cev'])
            completed_translations = sum(1 for completion in translation_completion.values() if completion >= 99.0)
            overall_completion = sum(translation_completion.values()) / len(translation_completion) if translation_completion else 0
            
            # Get file sizes for translation files (excluding WEB)
            translation_dir = Path('data/translations')
            file_sizes = {}
            bible_total_size = 0
            
            for translation_file in translation_dir.glob('bible_*.json'):
                translation_name = translation_file.stem.replace('bible_', '')
                if translation_name != 'web' and translation_file.exists():  # Exclude WEB
                    # Handle special case for NASB which uses nasb1995 file
                    display_name = translation_name
                    if translation_name == 'nasb1995':
                        display_name = 'nasb'  # Map nasb1995 file back to nasb key
                    
                    size_bytes = translation_file.stat().st_size
                    file_sizes[display_name] = {
                        'size_bytes': size_bytes,
                        'size_mb': round(size_bytes / (1024 * 1024), 2)
                    }
                    bible_total_size += size_bytes
            
            storage_stats = {
                'timestamp': datetime.now().isoformat(),
                'disk': {
                    'total_gb': round(total_gb, 2),
                    'used_gb': round(used_gb, 2),
                    'free_gb': round(free_gb, 2),
                    'used_percent': round(used_percent, 1),
                    'free_percent': round(free_percent, 1)
                },
                'translations': {
                    name: {
                        'completion': round(completion, 1),
                        'status': 'complete' if completion >= 99.0 else 'partial',
                        'file_info': file_sizes.get(name, {'size_bytes': 0, 'size_mb': 0})
                    }
                    for name, completion in translation_completion.items()
                },
                'bible_summary': {
                    'overall_completion': round(overall_completion, 1),
                    'completed_translations': completed_translations,
                    'total_translations': total_translations,
                    'total_size_mb': round(bible_total_size / (1024 * 1024), 2),
                    'total_size_bytes': bible_total_size
                }
            }
            
            return jsonify({'success': True, 'data': storage_stats})
        except Exception as e:
            current_app.logger.error(f"Storage stats API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/settings', methods=['GET'])
    def get_settings():
        """Get current settings."""
        try:
            settings = {
                'translation': current_app.verse_manager.get_configured_translation(),
                'display_mode': getattr(current_app.verse_manager, 'display_mode', 'time'),
                'time_format': getattr(current_app.verse_manager, 'time_format', '12'),
                'background_index': current_app.image_generator.current_background_index,
                'available_backgrounds': current_app.image_generator.get_available_backgrounds(),
                'available_translations': current_app.verse_manager.get_available_translations(),
                'translation_display_names': current_app.verse_manager.get_translation_display_names(),
                'parallel_mode': getattr(current_app.verse_manager, 'parallel_mode', False),
                'secondary_translation': current_app.verse_manager.get_configured_secondary_translation(),
                'available_fonts': current_app.image_generator.get_available_fonts(),
                'current_font': current_app.image_generator.get_current_font(),
                'font_sizes': current_app.image_generator.get_font_sizes(),
                'reference_position_info': current_app.image_generator.get_reference_position_info(),
                'voice_enabled': getattr(current_app.verse_manager, 'voice_enabled', False),
                'web_enabled': True,
                'auto_refresh': int(os.getenv('FORCE_REFRESH_INTERVAL', '60')),
                'hardware_mode': os.getenv('SIMULATION_MODE', 'false').lower() == 'false',
                'translation_completion': getattr(current_app.verse_manager, 'translation_completion', {}),
                # Enhanced layering data
                'enhanced_layering_enabled': current_app.image_generator.enhanced_layering_enabled,
                'separate_backgrounds': current_app.image_generator.get_available_separate_backgrounds() if hasattr(current_app.image_generator, 'get_available_separate_backgrounds') else [],
                'separate_borders': current_app.image_generator.get_available_separate_borders() if hasattr(current_app.image_generator, 'get_available_separate_borders') else [],
                'current_separate_background': current_app.image_generator.get_separate_background_info() if hasattr(current_app.image_generator, 'get_separate_background_info') else None,
                'current_separate_border': current_app.image_generator.get_separate_border_info() if hasattr(current_app.image_generator, 'get_separate_border_info') else None,
                # Display scaling
                'display_info': current_app.image_generator.get_display_info() if hasattr(current_app.image_generator, 'get_display_info') else None
            }
            
            return jsonify({'success': True, 'data': settings})
        except Exception as e:
            current_app.logger.error(f"Settings API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/settings', methods=['POST'])
    def update_settings():
        """Update settings."""
        try:
            data = request.get_json()
            
            # Track if we need to update the display
            needs_display_update = False
            
            # Update translation with validation
            if 'translation' in data:
                translation = data['translation']
                try:
                    available_translations = current_app.verse_manager.get_available_translations()
                    if translation in available_translations:
                        current_app.verse_manager.set_configured_translation(translation)
                        current_app.logger.info(f"Translation changed to: {translation}")
                        needs_display_update = True
                    else:
                        current_app.logger.error(f"Invalid translation: {translation}. Available: {available_translations}")
                        return jsonify({'success': False, 'error': f'Invalid translation: {translation}. Available translations: {", ".join(available_translations)}'}), 400
                except Exception as e:
                    current_app.logger.error(f"Translation validation error: {e}")
                    return jsonify({'success': False, 'error': f'Translation validation failed: {str(e)}'}), 500
            
            # Update display mode with validation
            if 'display_mode' in data:
                mode = data['display_mode']
                valid_modes = ['time', 'date', 'random', 'devotional', 'weather', 'news']
                try:
                    if mode in valid_modes:
                        current_app.verse_manager.display_mode = mode
                        current_app.logger.info(f"Display mode changed to: {mode}")
                        
                        # Track mode change in Bible Clock metrics
                        if hasattr(current_app, 'service_manager') and hasattr(current_app.service_manager, 'bible_metrics'):
                            try:
                                current_app.service_manager.bible_metrics.track_mode_change(mode)
                            except Exception as e:
                                current_app.logger.debug(f"Failed to track mode change: {e}")
                        
                        # Reset news service to start from article 1 when entering news mode
                        if mode == 'news':
                            try:
                                import sys
                                import os
                                sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
                                from news_service import news_service
                                news_service.reset_to_first_article()
                                current_app.logger.info("Reset news service to first article via web interface")
                            except Exception as e:
                                current_app.logger.warning(f"Could not reset news service via web interface: {e}")
                        
                        needs_display_update = True
                    else:
                        current_app.logger.error(f"Invalid display mode: {mode}. Valid modes: {valid_modes}")
                        return jsonify({'success': False, 'error': f'Invalid display mode: {mode}. Valid modes: {", ".join(valid_modes)}'}), 400
                except Exception as e:
                    current_app.logger.error(f"Display mode validation error: {e}")
                    return jsonify({'success': False, 'error': f'Display mode update failed: {str(e)}'}), 500
            
            # Update time format with validation
            if 'time_format' in data:
                time_format = data['time_format']
                valid_formats = ['12', '24']
                if time_format in valid_formats:
                    current_app.verse_manager.time_format = time_format
                    current_app.logger.info(f"Time format changed to: {time_format}")
                    needs_display_update = True
                else:
                    current_app.logger.error(f"Invalid time format: {time_format}. Valid formats: {valid_formats}")
                    return jsonify({'success': False, 'error': f'Invalid time format: {time_format}'}), 400
            
            # Update parallel mode
            if 'parallel_mode' in data:
                current_app.verse_manager.parallel_mode = data['parallel_mode']
                current_app.logger.info(f"Parallel mode: {data['parallel_mode']}")
            
            # Update secondary translation
            if 'secondary_translation' in data:
                current_app.verse_manager.set_configured_secondary_translation(data['secondary_translation'])
                current_app.logger.info(f"Secondary translation: {data['secondary_translation']}")
            
            # Update background with smart refresh detection
            background_changed = False
            if 'background_index' in data:
                old_bg_index = current_app.image_generator.current_background_index
                current_app.image_generator.set_background(data['background_index'])
                background_changed = (old_bg_index != current_app.image_generator.current_background_index)
                current_app.logger.info(f"Background changed to index: {data['background_index']} (changed: {background_changed})")
                needs_display_update = True  # Background changes need immediate update
            
            # Update font with validation
            if 'font' in data:
                font_name = data['font']
                try:
                    available_fonts = current_app.image_generator.get_available_fonts()
                    # available_fonts is a List[Dict] from get_available_fonts()
                    font_names = [font['name'] if isinstance(font, dict) else str(font) for font in available_fonts]
                    
                    if font_name in font_names or font_name == 'default':
                        current_app.image_generator.set_font(font_name)
                        current_app.logger.info(f"Font changed to: {font_name}")
                        needs_display_update = True
                    else:
                        current_app.logger.error(f"Invalid font: {font_name}. Available: {font_names}")
                        font_names_str = [str(name) for name in font_names]  # Ensure all items are strings
                        return jsonify({'success': False, 'error': f'Invalid font: {font_name}. Available fonts: {", ".join(font_names_str)}'}), 400
                        
                except Exception as e:
                    current_app.logger.error(f"Font validation error: {e}")
                    return jsonify({'success': False, 'error': f'Font update failed: {str(e)}'}), 500
            
            # Update font sizes
            if any(key in data for key in ['verse_size', 'reference_size']):
                current_app.image_generator.set_font_sizes(
                    verse_size=data.get('verse_size'),
                    reference_size=data.get('reference_size')
                )
                current_app.logger.info("Font sizes updated")
                needs_display_update = True  # Font size changes need immediate update
            
            # Update reference positioning
            if any(key in data for key in ['reference_position', 'reference_x_offset', 'reference_y_offset', 'reference_margin']):
                current_app.image_generator.set_reference_position(
                    position=data.get('reference_position', current_app.image_generator.reference_position),
                    x_offset=data.get('reference_x_offset', current_app.image_generator.reference_x_offset),
                    y_offset=data.get('reference_y_offset', current_app.image_generator.reference_y_offset),
                    margin=data.get('reference_margin', current_app.image_generator.reference_margin)
                )
                current_app.logger.info("Reference position updated")
                needs_display_update = True  # Position changes need immediate update
            
            # Update hardware mode
            if 'hardware_mode' in data:
                simulation_mode = 'false' if data['hardware_mode'] else 'true'
                os.environ['SIMULATION_MODE'] = simulation_mode
                # Update display manager simulation mode
                current_app.display_manager.simulation_mode = not data['hardware_mode']
                current_app.logger.info(f"Hardware mode: {'enabled' if data['hardware_mode'] else 'disabled (simulation)'}")
            
            # Update display scale
            if 'display_scale' in data:
                try:
                    scale = float(data['display_scale'])
                    current_app.image_generator.set_display_scale(scale)
                    current_app.logger.info(f"Display scale changed to: {scale}")
                    needs_display_update = True  # Scale changes need immediate update
                except (ValueError, TypeError) as e:
                    current_app.logger.error(f"Invalid display scale: {data['display_scale']}")
                    return jsonify({'success': False, 'error': f'Invalid display scale: {str(e)}'}), 400
            
            # Consolidated display update logic - update if requested OR if visual changes were made
            should_update_display = (
                data.get('update_display', False) or 
                needs_display_update or
                'background_index' in data or 
                'font' in data or 
                any(key in data for key in ['verse_size', 'reference_size', 'reference_position', 'reference_x_offset', 'reference_y_offset', 'reference_margin'])
            )
            
            if should_update_display:
                try:
                    verse_data = current_app.verse_manager.get_current_verse()
                    image = current_app.image_generator.create_verse_image(verse_data)
                    
                    # Determine refresh type: full refresh for background changes and parallel mode changes, partial for other settings
                    force_refresh = 'background_index' in data or background_changed or 'parallel_mode' in data
                    current_app.display_manager.display_image(image, force_refresh=force_refresh)
                    
                    if force_refresh:
                        if 'background_index' in data or background_changed:
                            refresh_type = "full (background change)"
                        elif 'parallel_mode' in data:
                            refresh_type = "full (parallel mode change)"
                        else:
                            refresh_type = "full (other change)"
                    else:
                        refresh_type = "partial (settings change)"
                    current_app.logger.info(f"Display updated immediately with {refresh_type}")
                    
                    # Track activity for recent activity log
                    _track_activity("Settings updated", f"Updated settings: {', '.join(data.keys())}")
                    
                except Exception as display_error:
                    current_app.logger.error(f"Display update failed: {display_error}")
                    # Don't fail the entire settings update for display issues
            
            return jsonify({'success': True, 'message': 'Settings updated successfully'})
            
        except Exception as e:
            current_app.logger.error(f"Settings update error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/backgrounds', methods=['GET'])
    def get_backgrounds():
        """Get available backgrounds with previews and cycling settings."""
        try:
            # Use enhanced layering system if available, otherwise fall back to legacy
            if hasattr(current_app.image_generator, 'enhanced_layering_enabled') and current_app.image_generator.enhanced_layering_enabled:
                # Return enhanced layering data for better UI experience
                backgrounds_list = current_app.image_generator.get_available_separate_backgrounds()
                backgrounds = {
                    'current_index': current_app.image_generator.separate_background_index,
                    'total_count': len(backgrounds_list),
                    'backgrounds': backgrounds_list
                }
            else:
                # Legacy system - filter to only show actual backgrounds, not borders
                legacy_info = current_app.image_generator.get_background_info()
                if 'backgrounds' in legacy_info:
                    filtered_backgrounds = [bg for bg in legacy_info['backgrounds'] if bg.get('type') == 'background']
                    backgrounds = {
                        'current_index': legacy_info.get('current_index', 0),
                        'total_count': len(filtered_backgrounds),
                        'backgrounds': filtered_backgrounds
                    }
                else:
                    backgrounds = legacy_info
            
            cycling_settings = current_app.image_generator.get_cycling_settings()
            backgrounds['cycling'] = cycling_settings
            return jsonify({'success': True, 'data': backgrounds})
        except Exception as e:
            current_app.logger.error(f"Backgrounds API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # Display Mode Management API Endpoints
    @app.route('/api/display-modes', methods=['GET'])
    def get_display_modes():
        """Get all display modes and their settings."""
        try:
            if not current_app.display_mode_manager:
                return jsonify({'success': False, 'error': 'Display mode manager not available'}), 500
            
            modes_info = current_app.display_mode_manager.get_all_modes_info()
            default_mode = current_app.display_mode_manager.get_default_mode()
            
            return jsonify({
                'success': True,
                'data': {
                    'modes': modes_info,
                    'default_mode': default_mode,
                    'available_modes': current_app.display_mode_manager.get_available_modes()
                }
            })
        except Exception as e:
            current_app.logger.error(f"Display modes API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/display-modes/default', methods=['POST'])
    def set_default_display_mode():
        """Set the default display mode for startup/restart."""
        try:
            if not current_app.display_mode_manager:
                return jsonify({'success': False, 'error': 'Display mode manager not available'}), 500
            
            data = request.get_json()
            mode = data.get('mode')
            
            if not mode:
                return jsonify({'success': False, 'error': 'Mode is required'}), 400
            
            current_app.display_mode_manager.set_default_mode(mode)
            
            return jsonify({
                'success': True,
                'message': f'Default mode set to {mode}',
                'default_mode': mode
            })
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"Set default mode error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/display-modes/<mode>/settings', methods=['GET'])
    def get_mode_settings(mode):
        """Get settings for a specific display mode."""
        try:
            if not current_app.display_mode_manager:
                return jsonify({'success': False, 'error': 'Display mode manager not available'}), 500
            
            settings = current_app.display_mode_manager.get_mode_settings(mode)
            if settings is None:
                return jsonify({'success': False, 'error': f'Mode {mode} not found'}), 404
            
            return jsonify({
                'success': True,
                'data': {
                    'mode': mode,
                    'settings': settings
                }
            })
        except Exception as e:
            current_app.logger.error(f"Get mode settings error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/display-modes/<mode>/settings', methods=['POST'])
    def update_mode_settings(mode):
        """Update settings for a specific display mode."""
        try:
            if not current_app.display_mode_manager:
                return jsonify({'success': False, 'error': 'Display mode manager not available'}), 500
            
            data = request.get_json()
            settings_update = data.get('settings', {})
            
            if not settings_update:
                return jsonify({'success': False, 'error': 'Settings are required'}), 400
            
            current_app.display_mode_manager.update_mode_settings(mode, settings_update)
            
            # If this is the current mode, apply settings immediately
            current_mode = getattr(current_app.verse_manager, 'display_mode', 'time')
            if mode == current_mode:
                current_app.display_mode_manager.apply_mode_settings_to_image_generator(
                    current_app.image_generator, mode
                )
            
            return jsonify({
                'success': True,
                'message': f'Settings updated for {mode} mode',
                'settings': current_app.display_mode_manager.get_mode_settings(mode)
            })
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"Update mode settings error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/display-modes/<mode>/reset', methods=['POST'])
    def reset_mode_to_defaults(mode):
        """Reset a display mode to its default settings."""
        try:
            if not current_app.display_mode_manager:
                return jsonify({'success': False, 'error': 'Display mode manager not available'}), 500
            
            current_app.display_mode_manager.reset_mode_to_defaults(mode)
            
            # If this is the current mode, apply default settings immediately
            current_mode = getattr(current_app.verse_manager, 'display_mode', 'time')
            if mode == current_mode:
                current_app.display_mode_manager.apply_mode_settings_to_image_generator(
                    current_app.image_generator, mode
                )
            
            return jsonify({
                'success': True,
                'message': f'{mode} mode reset to defaults',
                'settings': current_app.display_mode_manager.get_mode_settings(mode)
            })
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"Reset mode error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/fonts', methods=['GET'])
    def get_fonts():
        """Get available fonts."""
        try:
            fonts = current_app.image_generator.get_font_info()
            return jsonify({'success': True, 'data': fonts})
        except Exception as e:
            current_app.logger.error(f"Fonts API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/statistics', methods=['GET'])
    def get_statistics():
        """Get usage statistics."""
        try:
            # Get basic statistics from verse manager
            if hasattr(current_app.verse_manager, 'get_statistics'):
                stats = current_app.verse_manager.get_statistics()
            else:
                stats = _generate_basic_statistics()
            
            # Always provide safe AI statistics structure
            stats['ai_statistics'] = {
                'total_tokens': 0,
                'total_questions': 0,
                'total_cost': 0.0,
                'success_rate': 0,
                'avg_response_time': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'daily_usage': {}
            }
            
            # Try to get AI statistics if available, but don't fail if not
            try:
                if (hasattr(current_app.service_manager, 'voice_control') and 
                    current_app.service_manager.voice_control and 
                    hasattr(current_app.service_manager.voice_control, 'get_ai_statistics')):
                    ai_stats = current_app.service_manager.voice_control.get_ai_statistics()
                    stats['ai_statistics'].update(ai_stats)
            except Exception as ai_error:
                current_app.logger.debug(f"AI statistics not available: {ai_error}")
            
            # Add recent activities to statistics
            stats['recent_activities'] = getattr(current_app, 'recent_activities', [])
            
            return jsonify({'success': True, 'data': stats})
        except Exception as e:
            current_app.logger.error(f"Statistics API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/statistics/filtered', methods=['GET'])
    def get_filtered_statistics():
        """Get filtered statistics with time period and visualization support."""
        try:
            # Get filter parameters
            time_filter = request.args.get('filter', 'today')  # today, weekly, monthly, yearly, all_time
            date_reference = request.args.get('date_reference')
            
            # Only refresh if needed (not on every request to prevent data inconsistency)
            # current_app.time_aggregator.refresh_aggregations()
            
            # Get filtered data from time aggregator
            filtered_data = current_app.time_aggregator.get_filtered_data(time_filter, date_reference)
            
            # If no data found, return empty structure
            if not filtered_data:
                filtered_data = {
                    'total_conversations': 0,
                    'categories': {},
                    'keywords': {},
                    'avg_response_time': 0.0,
                    'success_rate': 100.0,
                    'hourly_distribution': {},
                    'daily_breakdown': {}
                }
            
            # Calculate total verses for time periods by summing from daily data
            total_verses = 0
            if time_filter in ['today', 'weekly', 'monthly', 'yearly'] and filtered_data:
                start_date = filtered_data.get('start_date')
                end_date = filtered_data.get('end_date')
                
                # For 'today', get today's date if not provided
                if time_filter == 'today' and not start_date:
                    today = datetime.now().date().isoformat()
                    start_date = today
                    end_date = today
                
                if start_date and end_date:
                    # Load daily metrics to get verse counts
                    try:
                        daily_metrics_file = Path('data/daily_metrics.json')
                        if daily_metrics_file.exists():
                            with open(daily_metrics_file, 'r') as f:
                                daily_metrics = json.load(f)
                            
                            # Sum verses for the date range
                            start_dt = datetime.fromisoformat(start_date).date()
                            end_dt = datetime.fromisoformat(end_date).date()
                            current_dt = start_dt
                            
                            while current_dt <= end_dt:
                                date_key = current_dt.isoformat()
                                day_data = daily_metrics.get(date_key, {})
                                total_verses += day_data.get('verses_displayed_today', 0)
                                current_dt += timedelta(days=1)
                                
                    except Exception as e:
                        current_app.logger.warning(f"Could not calculate verses for {time_filter}: {e}")
                        # Fallback to conversation count if verses calculation fails
                        total_verses = filtered_data.get('total_conversations', 0)
            else:
                # For 'all_time', use existing logic
                total_verses = filtered_data.get('total_conversations', 0)

            # Format data for frontend consumption
            formatted_data = {
                'period_info': {
                    'filter': time_filter,
                    'period_key': filtered_data.get('period_key', time_filter),
                    'start_date': filtered_data.get('start_date'),
                    'end_date': filtered_data.get('end_date')
                },
                'conversations': {
                    'total': total_verses,  # Now correctly shows verse count
                    'categories': filtered_data.get('categories', {}),
                    'success_rate': filtered_data.get('success_rate', 100.0)
                },
                'performance': {
                    'avg_response_time': filtered_data.get('avg_response_time', 0.0)
                },
                'keywords': filtered_data.get('keywords', {}),
                'hourly_distribution': filtered_data.get('hourly_distribution', {}),
                'daily_breakdown': filtered_data.get('daily_breakdown', {}),
                'mode_usage_hours': filtered_data.get('mode_usage_hours', {}),
                'total_verses': total_verses  # Add explicit field for verses
            }
            
            return jsonify({'success': True, 'data': formatted_data})
        except Exception as e:
            current_app.logger.error(f"Filtered statistics API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/statistics/visualization', methods=['GET'])
    def get_statistics_visualization():
        """Get visualization data for charts and graphs."""
        try:
            stats = current_app.verse_manager.get_statistics()
            
            # Extract visualization data
            visualization_data = {
                'book_chapter_data': stats.get('enhanced', {}).get('book_chapter_visualization', {}),
                'timeline_data': stats.get('enhanced', {}).get('timeline_data', {}),
                'filter_summaries': stats.get('enhanced', {}).get('filter_summaries', {}),
                'chart_ready': True
            }
            
            return jsonify({'success': True, 'data': visualization_data})
        except Exception as e:
            current_app.logger.error(f"Visualization statistics API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/statistics/charts', methods=['GET'])
    def get_chart_data():
        """Get chart data for specific time filter and chart type."""
        try:
            time_filter = request.args.get('filter', 'today')
            chart_type = request.args.get('type', 'categories')
            date_reference = request.args.get('date_reference')
            
            # Only refresh if needed (not on every request to prevent data inconsistency)
            # current_app.time_aggregator.refresh_aggregations()
            
            # For mobile compatibility, return full filtered data instead of specific chart data
            if not chart_type or chart_type == 'categories':
                # Get full filtered data for mobile charts
                filtered_data = current_app.time_aggregator.get_filtered_data(time_filter, date_reference)
                
                # Map the fields to what mobile expects
                chart_data = {
                    'mode_usage': filtered_data.get('categories', {}),
                    'translation_usage': filtered_data.get('translation_usage', {}),
                    'bible_books_accessed': filtered_data.get('bible_books_accessed', {})
                }
                
                return jsonify({'success': True, 'data': chart_data})
            else:
                # Get specific chart data from time aggregator
                chart_data = current_app.time_aggregator.get_chart_data(time_filter, chart_type, date_reference)
                return jsonify({'success': True, 'data': chart_data})
                
        except Exception as e:
            current_app.logger.error(f"Chart data API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/statistics/books', methods=['GET'])
    def get_books_paginated():
        """Get paginated Bible books accessed data."""
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 10))
            time_filter = request.args.get('filter', 'today')
            view_type = request.args.get('view', 'data')  # 'data' or 'chart'
            
            # Get statistics data
            stats = current_app.verse_manager.get_statistics()
            books_accessed = stats.get('books_accessed', [])
            
            # Convert to book data with counts (mock data for now until we have actual counts)
            book_data = []
            for i, book in enumerate(books_accessed):
                book_data.append({
                    'name': book,
                    'count': max(len(books_accessed) - i, 1),  # Mock decreasing count
                    'percentage': round((max(len(books_accessed) - i, 1) / len(books_accessed)) * 100, 1) if books_accessed else 0
                })
            
            # Sort by count (descending order as requested)
            book_data.sort(key=lambda x: x['count'], reverse=True)
            
            # Calculate pagination
            total_books = len(book_data)
            total_pages = max(1, (total_books + per_page - 1) // per_page)
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, total_books)
            
            paginated_books = book_data[start_idx:end_idx]
            
            return jsonify({
                'success': True,
                'data': {
                    'books': paginated_books,
                    'pagination': {
                        'current_page': page,
                        'per_page': per_page,
                        'total_pages': total_pages,
                        'total_books': total_books,
                        'has_next': page < total_pages,
                        'has_prev': page > 1,
                        'next_page': page + 1 if page < total_pages else None,
                        'prev_page': page - 1 if page > 1 else None
                    }
                }
            })
        except Exception as e:
            current_app.logger.error(f"Books pagination API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/statistics/clean-random', methods=['POST'])
    def clean_random_statistics():
        """Remove 'random' entries from translation usage statistics."""
        try:
            removed_count = current_app.verse_manager.clean_random_from_statistics()
            if removed_count > 0:
                current_app.logger.info(f"Cleaned up {removed_count} random translation statistics")
                return jsonify({'success': True, 'message': f'Removed {removed_count} random translation entries'})
            else:
                return jsonify({'success': True, 'message': 'No random translation entries found to clean'})
        except Exception as e:
            current_app.logger.error(f"Clean random statistics API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/refresh', methods=['POST'])
    def force_refresh():
        """Force display refresh."""
        try:
            verse_data = current_app.verse_manager.get_current_verse()
            image = current_app.image_generator.create_verse_image(verse_data)
            current_app.display_manager.display_image(image, force_refresh=True)
            
            _track_activity("Display refreshed", f"Manual refresh triggered for {verse_data.get('reference', 'Unknown')}")
            return jsonify({'success': True, 'message': 'Display refreshed'})
        except Exception as e:
            current_app.logger.error(f"Refresh error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/clear-ghosting', methods=['POST'])
    def clear_ghosting():
        """Clear display ghosting artifacts."""
        try:
            if hasattr(current_app.display_manager, 'clear_ghosting'):
                current_app.display_manager.clear_ghosting()
                _track_activity("Display ghosting cleared", "Aggressive ghosting removal performed")
                return jsonify({'success': True, 'message': 'Display ghosting cleared'})
            else:
                # Fallback to multiple full refreshes
                for i in range(3):
                    verse_data = current_app.verse_manager.get_current_verse()
                    image = current_app.image_generator.create_verse_image(verse_data)
                    current_app.display_manager.display_image(image, force_refresh=True)
                    if i < 2:  # Don't sleep after last refresh
                        import time
                        time.sleep(1)
                
                _track_activity("Display cleared", "Multiple refresh cycles performed")
                return jsonify({'success': True, 'message': 'Display cleared with multiple refreshes'})
        except Exception as e:
            current_app.logger.error(f"Clear ghosting error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/force-clear-artifacts', methods=['POST'])
    def force_clear_artifacts():
        """Force clear display artifacts."""
        try:
            if hasattr(current_app.display_manager, 'force_clear_artifacts'):
                current_app.display_manager.force_clear_artifacts()
                _track_activity("Display artifacts cleared", "Force clear artifacts performed")
                return jsonify({'success': True, 'message': 'Display artifacts cleared successfully'})
            else:
                # Fallback to aggressive clearing
                current_app.display_manager.clear_display()
                _track_activity("Display cleared", "Fallback clear performed")
                return jsonify({'success': True, 'message': 'Display cleared with fallback method'})
        except Exception as e:
            current_app.logger.error(f"Force clear artifacts error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/background/cycle', methods=['POST'])
    def cycle_background():
        """Cycle to next background with smart refresh."""
        try:
            current_app.image_generator.cycle_background()
            
            # Update display if requested - always use full refresh for background changes
            if request.get_json() and request.get_json().get('update_display', False):
                verse_data = current_app.verse_manager.get_current_verse()
                image = current_app.image_generator.create_verse_image(verse_data)
                current_app.display_manager.display_image(image, force_refresh=True)
                current_app.logger.info("Background cycled with full refresh")
                _track_activity("Background cycled", f"Background changed to index {current_app.image_generator.current_background_index}")
            
            return jsonify({
                'success': True, 
                'message': 'Background cycled',
                'current_background': current_app.image_generator.get_current_background_info()
            })
        except Exception as e:
            current_app.logger.error(f"Background cycle error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/background/randomize', methods=['POST'])
    def randomize_background():
        """Randomize background with smart refresh."""
        try:
            current_app.image_generator.randomize_background()
            
            # Update display if requested - always use full refresh for background changes
            if request.get_json() and request.get_json().get('update_display', False):
                verse_data = current_app.verse_manager.get_current_verse()
                image = current_app.image_generator.create_verse_image(verse_data)
                current_app.display_manager.display_image(image, force_refresh=True)
                current_app.logger.info("Background randomized with full refresh")
            
            return jsonify({
                'success': True, 
                'message': 'Background randomized',
                'current_background': current_app.image_generator.get_current_background_info()
            })
        except Exception as e:
            current_app.logger.error(f"Background randomize error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/background/cycling', methods=['POST'])
    def set_background_cycling():
        """Configure background cycling settings."""
        try:
            data = request.get_json()
            enabled = data.get('enabled', False)
            interval = data.get('interval_minutes', 30)
            
            current_app.image_generator.set_background_cycling(enabled, interval)
            
            return jsonify({
                'success': True,
                'message': 'Background cycling updated',
                'settings': current_app.image_generator.get_cycling_settings()
            })
        except Exception as e:
            current_app.logger.error(f"Background cycling error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # Enhanced Layering API Endpoints
    @app.route('/api/enhanced-layering/backgrounds', methods=['GET'])
    def get_separate_backgrounds():
        """Get available backgrounds for enhanced layering."""
        try:
            backgrounds = current_app.image_generator.get_available_separate_backgrounds()
            current_info = current_app.image_generator.get_separate_background_info()
            
            return jsonify({
                'success': True,
                'data': {
                    'backgrounds': backgrounds,
                    'current': current_info,
                    'enhanced_layering_enabled': current_app.image_generator.enhanced_layering_enabled
                }
            })
        except Exception as e:
            current_app.logger.error(f"Get separate backgrounds error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/enhanced-layering/borders', methods=['GET'])
    def get_separate_borders():
        """Get available borders for enhanced layering."""
        try:
            borders = current_app.image_generator.get_available_separate_borders()
            current_info = current_app.image_generator.get_separate_border_info()
            
            return jsonify({
                'success': True,
                'data': {
                    'borders': borders,
                    'current': current_info,
                    'enhanced_layering_enabled': current_app.image_generator.enhanced_layering_enabled
                }
            })
        except Exception as e:
            current_app.logger.error(f"Get separate borders error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/enhanced-layering/set-background', methods=['POST'])
    def set_separate_background():
        """Set background for enhanced layering."""
        try:
            data = request.get_json()
            index = data.get('index', 0)
            
            current_app.image_generator.set_separate_background(index)
            
            # Update display if requested
            if data.get('update_display', False):
                verse_data = current_app.verse_manager.get_current_verse()
                image = current_app.image_generator.create_verse_image(verse_data)
                current_app.display_manager.display_image(image, force_refresh=True)
                current_app.logger.info("Display updated with new background")
            
            return jsonify({
                'success': True,
                'message': 'Background updated',
                'current': current_app.image_generator.get_separate_background_info()
            })
        except Exception as e:
            current_app.logger.error(f"Set separate background error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/enhanced-layering/set-border', methods=['POST'])
    def set_separate_border():
        """Set border for enhanced layering."""
        try:
            data = request.get_json()
            index = data.get('index', 0)
            
            current_app.image_generator.set_separate_border(index)
            
            # Update display if requested
            if data.get('update_display', False):
                verse_data = current_app.verse_manager.get_current_verse()
                image = current_app.image_generator.create_verse_image(verse_data)
                current_app.display_manager.display_image(image, force_refresh=True)
                current_app.logger.info("Display updated with new border")
            
            return jsonify({
                'success': True,
                'message': 'Border updated',
                'current': current_app.image_generator.get_separate_border_info()
            })
        except Exception as e:
            current_app.logger.error(f"Set separate border error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/enhanced-layering/toggle', methods=['POST'])
    def toggle_enhanced_layering():
        """Toggle enhanced layering mode."""
        try:
            data = request.get_json()
            enabled = data.get('enabled', None)
            
            result = current_app.image_generator.toggle_enhanced_layering(enabled)
            
            return jsonify({
                'success': True,
                'message': f'Enhanced layering {"enabled" if result else "disabled"}',
                'enhanced_layering_enabled': result
            })
        except Exception as e:
            current_app.logger.error(f"Toggle enhanced layering error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/preview', methods=['POST'])
    def preview_settings():
        """Preview settings without applying to display."""
        try:
            data = request.get_json()
            
            # Store original settings
            original_translation = current_app.verse_manager.translation
            original_display_mode = getattr(current_app.verse_manager, 'display_mode', 'time')
            original_parallel_mode = getattr(current_app.verse_manager, 'parallel_mode', False)
            original_secondary_translation = getattr(current_app.verse_manager, 'secondary_translation', 'amp')
            original_background_index = current_app.image_generator.current_background_index
            original_font = current_app.image_generator.current_font_name
            original_font_sizes = current_app.image_generator.get_font_sizes()
            
            try:
                # Apply temporary changes
                if 'translation' in data:
                    current_app.verse_manager.translation = data['translation']
                
                if 'display_mode' in data:
                    mode = data['display_mode']
                    current_app.verse_manager.display_mode = mode
                    
                    # Reset news service to start from article 1 when entering news mode
                    if mode == 'news':
                        try:
                            import sys
                            import os
                            sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
                            from news_service import news_service
                            news_service.reset_to_first_article()
                            current_app.logger.info("Reset news service to first article via preview")
                        except Exception as e:
                            current_app.logger.warning(f"Could not reset news service via preview: {e}")
                    
                    # Apply mode-specific settings if display mode manager is available
                    if current_app.display_mode_manager:
                        try:
                            current_app.display_mode_manager.apply_mode_settings_to_image_generator(
                                current_app.image_generator, mode
                            )
                            current_app.logger.info(f"Applied {mode} mode settings")
                        except Exception as e:
                            current_app.logger.error(f"Error applying {mode} mode settings: {e}")
                
                if 'parallel_mode' in data:
                    current_app.verse_manager.parallel_mode = data['parallel_mode']
                
                if 'secondary_translation' in data:
                    current_app.verse_manager.secondary_translation = data['secondary_translation']
                
                if 'background_index' in data:
                    bg_index = data['background_index']
                    if 0 <= bg_index < len(current_app.image_generator.background_files):
                        current_app.image_generator.current_background_index = bg_index
                    else:
                        current_app.logger.warning(f"Invalid background index: {bg_index}")
                        current_app.image_generator.current_background_index = 0
                
                if 'font' in data:
                    current_app.image_generator.current_font_name = data['font']
                    current_app.image_generator._load_fonts_with_selection()
                
                if 'font_sizes' in data:
                    sizes = data['font_sizes']
                    current_app.image_generator.set_font_sizes(
                        verse_size=sizes.get('verse_size'),
                        reference_size=sizes.get('reference_size')
                    )
                
                # Generate preview
                verse_data = current_app.verse_manager.get_current_verse()
                image = current_app.image_generator.create_verse_image(verse_data)
                
                # Apply same transformations as actual display for accurate preview
                preview_image = _apply_display_transformations(image)
                
                # Save preview image
                preview_path = Path('src/web_interface/static/preview.png')
                preview_path.parent.mkdir(exist_ok=True)
                preview_image.save(preview_path)
                
                # Schedule cleanup of old preview images
                _cleanup_old_preview_images()
                
                # Return success with metadata
                return jsonify({
                    'success': True, 
                    'preview_url': f'/static/preview.png?t={datetime.now().timestamp()}',
                    'timestamp': datetime.now().isoformat(),
                    'background_name': f"Background {current_app.image_generator.current_background_index + 1}",
                    'font_name': current_app.image_generator.current_font_name,
                    'verse_reference': verse_data.get('reference', 'Unknown')
                })
                
            finally:
                # Restore original settings
                current_app.verse_manager.translation = original_translation
                current_app.verse_manager.display_mode = original_display_mode
                current_app.verse_manager.parallel_mode = original_parallel_mode
                current_app.verse_manager.secondary_translation = original_secondary_translation
                current_app.image_generator.current_background_index = original_background_index
                current_app.image_generator.current_font_name = original_font
                current_app.image_generator.set_font_sizes(
                    verse_size=original_font_sizes['verse_size'],
                    reference_size=original_font_sizes['reference_size']
                )
            
        except Exception as e:
            current_app.logger.error(f"Preview error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/status', methods=['GET'])
    def get_voice_status():
        """Get voice control status."""
        try:
            if hasattr(current_app.service_manager, 'voice_control') and current_app.service_manager.voice_control:
                status = current_app.service_manager.voice_control.get_voice_status()
                # Add wake_word_enabled field for mobile compatibility
                if 'enabled' in status:
                    status['wake_word_enabled'] = status['enabled']
                
                # Add TTS settings from environment for OpenAI TTS compatibility
                import os
                tts_volume = os.getenv('TTS_VOLUME', os.getenv('VOICE_VOLUME', '0.8'))
                tts_playback_mode = os.getenv('TTS_PLAYBACK_MODE', 'audio')
                status['tts_volume'] = float(tts_volume)
                status['tts_playback_mode'] = tts_playback_mode
                
                return jsonify({'success': True, 'data': status})
            else:
                return jsonify({
                    'success': True, 
                    'data': {
                        'enabled': False,
                        'wake_word_enabled': False,
                        'listening': False,
                        'chatgpt_enabled': False,
                        'help_enabled': False,
                        'message': 'Voice control not initialized'
                    }
                })
        except Exception as e:
            current_app.logger.error(f"Voice status API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/test', methods=['POST'])
    def test_voice():
        """Test voice synthesis."""
        try:
            if hasattr(current_app.service_manager, 'voice_control') and current_app.service_manager.voice_control:
                current_app.service_manager.voice_control.test_voice_synthesis()
                return jsonify({'success': True, 'message': 'Voice test initiated'})
            else:
                return jsonify({'success': False, 'error': 'Voice control not available'})
        except Exception as e:
            current_app.logger.error(f"Voice test API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/clear-history', methods=['POST'])
    def clear_voice_history():
        """Clear ChatGPT conversation history."""
        try:
            if hasattr(current_app.service_manager, 'voice_control') and current_app.service_manager.voice_control:
                current_app.service_manager.voice_control.clear_conversation_history()
                return jsonify({'success': True, 'message': 'Conversation history cleared'})
            else:
                return jsonify({'success': False, 'error': 'Voice control not available'})
        except Exception as e:
            current_app.logger.error(f"Clear history API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/history', methods=['GET'])
    def get_voice_history():
        """Get conversation history."""
        try:
            if hasattr(current_app.service_manager, 'voice_control') and current_app.service_manager.voice_control:
                history = current_app.service_manager.voice_control.get_conversation_history()
                return jsonify({'success': True, 'data': history})
            else:
                return jsonify({'success': True, 'data': []})
        except Exception as e:
            current_app.logger.error(f"Voice history API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/settings', methods=['POST'])
    def update_voice_settings():
        """Update voice control settings."""
        try:
            if not hasattr(current_app.service_manager, 'voice_control') or not current_app.service_manager.voice_control:
                return jsonify({'success': False, 'error': 'Voice control not available'})
            
            data = request.get_json()
            voice_control = current_app.service_manager.voice_control
            
            # Update settings
            if 'voice_rate' in data:
                voice_control.voice_rate = data['voice_rate']
                if voice_control.tts_engine:
                    voice_control.tts_engine.setProperty('rate', data['voice_rate'])
            
            if 'voice_volume' in data:
                voice_control.voice_volume = data['voice_volume']
                if voice_control.tts_engine:
                    voice_control.tts_engine.setProperty('volume', data['voice_volume'])
                
                # Also update TTS_VOLUME in environment for OpenAI TTS (VoiceAssistant)
                import os
                try:
                    # Update TTS_VOLUME for the current session
                    os.environ['TTS_VOLUME'] = str(data['voice_volume'])
                    # Also update PIPER_VOICE_VOLUME for Piper TTS
                    os.environ['PIPER_VOICE_VOLUME'] = str(data['voice_volume'])
                    
                    # Update .env file to persist the setting
                    env_path = '.env'
                    if os.path.exists(env_path):
                        with open(env_path, 'r') as f:
                            lines = f.readlines()
                        
                        # Update or add TTS_VOLUME and PIPER_VOICE_VOLUME lines
                        tts_volume_updated = False
                        piper_volume_updated = False
                        
                        for i, line in enumerate(lines):
                            if line.startswith('TTS_VOLUME='):
                                lines[i] = f'TTS_VOLUME={data["voice_volume"]}\n'
                                tts_volume_updated = True
                            elif line.startswith('PIPER_VOICE_VOLUME='):
                                lines[i] = f'PIPER_VOICE_VOLUME={data["voice_volume"]}\n'
                                piper_volume_updated = True
                        
                        # Add missing volume settings
                        if not tts_volume_updated or not piper_volume_updated:
                            for i, line in enumerate(lines):
                                if line.startswith('TTS_AUDIO_FORMAT='):
                                    if not tts_volume_updated:
                                        lines.insert(i + 1, f'TTS_VOLUME={data["voice_volume"]}\n')
                                        i += 1
                                    if not piper_volume_updated:
                                        lines.insert(i + 1, f'PIPER_VOICE_VOLUME={data["voice_volume"]}\n')
                                    break
                        
                        with open(env_path, 'w') as f:
                            f.writelines(lines)
                        
                        current_app.logger.info(f"Updated TTS_VOLUME to {data['voice_volume']} in .env file")
                    
                    # Update VoiceAssistant volume settings if available
                    if hasattr(current_app.service_manager, 'voice_control') and hasattr(current_app.service_manager.voice_control, 'update_volume_settings'):
                        current_app.service_manager.voice_control.update_volume_settings(data['voice_volume'])
                    
                except Exception as env_error:
                    current_app.logger.error(f"Failed to update TTS_VOLUME in .env: {env_error}")
            
            # Handle TTS playback mode setting
            if 'tts_playback_mode' in data:
                import os
                try:
                    playback_mode = data['tts_playback_mode']
                    if playback_mode in ['audio', 'visual']:
                        # Update TTS_PLAYBACK_MODE for the current session
                        os.environ['TTS_PLAYBACK_MODE'] = playback_mode
                        
                        # Update .env file to persist the setting
                        env_path = '.env'
                        if os.path.exists(env_path):
                            with open(env_path, 'r') as f:
                                lines = f.readlines()
                            
                            # Update or add TTS_PLAYBACK_MODE line
                            playback_mode_updated = False
                            for i, line in enumerate(lines):
                                if line.startswith('TTS_PLAYBACK_MODE='):
                                    lines[i] = f'TTS_PLAYBACK_MODE={playback_mode}\n'
                                    playback_mode_updated = True
                                    break
                            
                            if not playback_mode_updated:
                                # Add TTS_PLAYBACK_MODE line after TTS_VOLUME
                                for i, line in enumerate(lines):
                                    if line.startswith('TTS_VOLUME='):
                                        lines.insert(i + 1, f'TTS_PLAYBACK_MODE={playback_mode}\n')
                                        break
                            
                            with open(env_path, 'w') as f:
                                f.writelines(lines)
                            
                            current_app.logger.info(f"Updated TTS_PLAYBACK_MODE to {playback_mode} in .env file")
                        
                except Exception as playback_error:
                    current_app.logger.error(f"Failed to update TTS_PLAYBACK_MODE in .env: {playback_error}")
            
            # Handle API key FIRST before enabling ChatGPT
            if 'chatgpt_api_key' in data:
                # Update the OpenAI API key
                api_key = data['chatgpt_api_key']
                if api_key and not api_key.startswith('•'):  # Not a masked value
                    voice_control.openai_api_key = api_key
                    # Re-initialize ChatGPT with the new key
                    voice_control._initialize_chatgpt()
                    current_app.logger.info("ChatGPT API key updated")
            
            # Now handle ChatGPT enabled/disabled AFTER API key is set
            if 'chatgpt_enabled' in data:
                # For VoiceAssistant, chatgpt_enabled is controlled by the enabled property
                # and the presence of an API key. We can't set it directly.
                if hasattr(voice_control, 'set_chatgpt_enabled'):
                    voice_control.set_chatgpt_enabled(data['chatgpt_enabled'])
                else:
                    # For VoiceAssistant class, use the new chatgpt_enabled property
                    voice_control.chatgpt_enabled = data['chatgpt_enabled']
            
            if 'help_enabled' in data:
                voice_control.help_enabled = data['help_enabled']
            
            # Handle audio input/output controls
            if 'audio_input_enabled' in data:
                voice_control.audio_input_enabled = data['audio_input_enabled']
                current_app.logger.info(f"Audio input: {'enabled' if data['audio_input_enabled'] else 'disabled'}")
            
            if 'audio_output_enabled' in data:
                voice_control.audio_output_enabled = data['audio_output_enabled']
                current_app.logger.info(f"Audio output: {'enabled' if data['audio_output_enabled'] else 'disabled'}")
            
            if 'screen_display_enabled' in data:
                voice_control.screen_display_enabled = data['screen_display_enabled']
                current_app.logger.info(f"Screen display: {'enabled' if data['screen_display_enabled'] else 'disabled'}")
            
            # Handle voice control enabled/disabled
            if 'voice_control_enabled' in data:
                import os  # Ensure os is available in this scope
                voice_control.enabled = data['voice_control_enabled']
                # Also update the environment variable
                os.environ['ENABLE_VOICE'] = 'true' if data['voice_control_enabled'] else 'false'
                current_app.logger.info(f"Voice control: {'enabled' if data['voice_control_enabled'] else 'disabled'}")
                
                # Also update the .env file to persist the setting
                try:
                    env_path = '.env'
                    if os.path.exists(env_path):
                        with open(env_path, 'r') as f:
                            lines = f.readlines()
                        
                        # Update ENABLE_VOICE line
                        voice_enabled_updated = False
                        for i, line in enumerate(lines):
                            if line.startswith('ENABLE_VOICE='):
                                lines[i] = f'ENABLE_VOICE={"true" if data["voice_control_enabled"] else "false"}\n'
                                voice_enabled_updated = True
                                break
                        
                        if not voice_enabled_updated:
                            # Add ENABLE_VOICE line if it doesn't exist
                            lines.append(f'ENABLE_VOICE={"true" if data["voice_control_enabled"] else "false"}\n')
                        
                        with open(env_path, 'w') as f:
                            f.writelines(lines)
                        
                        current_app.logger.info(f"Updated ENABLE_VOICE in .env file to {data['voice_control_enabled']}")
                except Exception as env_error:
                    current_app.logger.error(f"Failed to update ENABLE_VOICE in .env: {env_error}")
            
            if 'voice_selection' in data:
                voice_control.voice_selection = data['voice_selection']
                selection = data['voice_selection']
                
                # For OpenAI TTS, update the voice directly
                if hasattr(voice_control, 'tts_voice') and selection in ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']:
                    voice_control.tts_voice = selection
                    current_app.logger.info(f"OpenAI TTS voice updated to: {selection}")
                    
                    # Update environment variable for persistence
                    import os
                    os.environ['TTS_VOICE'] = selection
                    
                    # Update .env file for persistence across restarts
                    try:
                        env_file_path = '/home/admin/Bible-Clock-v3/.env'
                        if os.path.exists(env_file_path):
                            with open(env_file_path, 'r') as f:
                                lines = f.readlines()
                            
                            # Update or add TTS_VOICE line
                            updated = False
                            for i, line in enumerate(lines):
                                if line.startswith('TTS_VOICE='):
                                    lines[i] = f'TTS_VOICE={selection}\n'
                                    updated = True
                                    break
                            
                            if not updated:
                                lines.append(f'TTS_VOICE={selection}\n')
                            
                            with open(env_file_path, 'w') as f:
                                f.writelines(lines)
                            
                            current_app.logger.info(f"Updated .env file with TTS_VOICE={selection}")
                    except Exception as e:
                        current_app.logger.warning(f"Could not update .env file: {e}")
                
                # Legacy system TTS fallback (for compatibility)
                elif voice_control.tts_engine:
                    voices = voice_control.tts_engine.getProperty('voices')
                    if voices:
                        if selection == 'female':
                            female_voices = [v for v in voices if 'female' in v.name.lower() or 'woman' in v.name.lower()]
                            if female_voices:
                                voice_control.tts_engine.setProperty('voice', female_voices[0].id)
                        elif selection == 'male':
                            male_voices = [v for v in voices if 'male' in v.name.lower() or 'man' in v.name.lower()]
                            if male_voices:
                                voice_control.tts_engine.setProperty('voice', male_voices[0].id)
            
            return jsonify({'success': True, 'message': 'Voice settings updated successfully'})
            
        except Exception as e:
            current_app.logger.error(f"Voice settings API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # === Conversation Analytics API ===
    
    @app.route('/api/conversation/analytics', methods=['GET'])
    def get_conversation_analytics():
        """Get conversation analytics and metrics."""
        try:
            days_back = request.args.get('days', 7, type=int)
            analytics = current_app.conversation_manager.get_analytics(days_back)
            return jsonify({'success': True, 'data': analytics})
        except Exception as e:
            current_app.logger.error(f"Conversation analytics API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/conversation/sessions', methods=['GET'])
    def get_conversation_sessions():
        """Get active conversation sessions."""
        try:
            active_sessions = [
                {
                    'session_id': session.session_id,
                    'created_at': session.created_at.isoformat(),
                    'last_activity': session.last_activity.isoformat(),
                    'turn_count': len(session.turns),
                    'is_current': session.session_id == current_app.conversation_manager.current_session.session_id if current_app.conversation_manager.current_session else False
                }
                for session in current_app.conversation_manager.sessions.values()
                if not session.is_expired()
            ]
            return jsonify({'success': True, 'data': active_sessions})
        except Exception as e:
            current_app.logger.error(f"Conversation sessions API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/conversation/suggestions', methods=['GET'])
    def get_bible_study_suggestions():
        """Get Bible study suggestions based on conversation history."""
        try:
            suggestions = current_app.conversation_manager.get_bible_study_suggestions()
            return jsonify({'success': True, 'data': suggestions})
        except Exception as e:
            current_app.logger.error(f"Bible study suggestions API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/conversation/memory', methods=['GET'])
    def get_conversation_memory():
        """Get conversation context/memory for current session."""
        try:
            context = current_app.conversation_manager.get_conversation_context(turns_back=5)
            return jsonify({'success': True, 'data': {'context': context}})
        except Exception as e:
            current_app.logger.error(f"Conversation memory API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # === Piper Voice Management API ===
    
    @app.route('/api/voice/piper/voices', methods=['GET'])
    def get_piper_voices():
        """Get available Piper TTS voices."""
        try:
            import os
            import glob
            from pathlib import Path
            
            voices_dir = Path.home() / ".local" / "share" / "piper" / "voices"
            available_voices = []
            
            if voices_dir.exists():
                # Find all .onnx voice model files
                voice_files = glob.glob(str(voices_dir / "*.onnx"))
                
                for voice_file in voice_files:
                    voice_name = os.path.basename(voice_file).replace('.onnx', '')
                    config_file = voice_file + '.json'
                    
                    # Get voice info from config if available
                    voice_info = {
                        'name': voice_name,
                        'display_name': _format_voice_name(voice_name),
                        'file_path': voice_file,
                        'available': os.path.exists(voice_file)
                    }
                    
                    # Read config for additional info
                    if os.path.exists(config_file):
                        try:
                            import json
                            with open(config_file, 'r') as f:
                                config = json.load(f)
                                voice_info.update({
                                    'language': config.get('language', 'en_US'),
                                    'quality': config.get('quality', 'medium'),
                                    'sample_rate': config.get('audio', {}).get('sample_rate', 22050),
                                    'speaker_id': config.get('speaker_id_map', {})
                                })
                        except:
                            pass
                    
                    available_voices.append(voice_info)
            
            # Sort voices by name
            available_voices.sort(key=lambda x: x['display_name'])
            
            return jsonify({
                'success': True,
                'data': {
                    'voices': available_voices,
                    'voices_dir': str(voices_dir),
                    'current_voice': _get_current_piper_voice()
                }
            })
            
        except Exception as e:
            current_app.logger.error(f"Piper voices API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/piper/preview', methods=['POST'])
    def preview_piper_voice():
        """Preview a Piper TTS voice."""
        try:
            data = request.get_json()
            if not data or 'voice_name' not in data:
                return jsonify({'success': False, 'error': 'Voice name required'}), 400
            
            voice_name = data['voice_name']
            preview_text = data.get('text', "For God so loved the world that he gave his one and only Son.")
            
            import subprocess
            import tempfile
            import os
            from pathlib import Path
            
            # Get voice model path
            voices_dir = Path.home() / ".local" / "share" / "piper" / "voices"
            voice_model = voices_dir / f"{voice_name}.onnx"
            
            if not voice_model.exists():
                return jsonify({'success': False, 'error': f'Voice model not found: {voice_name}'}), 404
            
            # Generate speech
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                # Try to find piper binary
                piper_cmd = None
                for cmd in ['piper', '/usr/local/bin/piper', './piper/piper']:
                    try:
                        result = subprocess.run([cmd, '--help'], capture_output=True, timeout=5)
                        if result.returncode == 0:
                            piper_cmd = cmd
                            break
                    except:
                        continue
                
                if not piper_cmd:
                    return jsonify({'success': False, 'error': 'Piper TTS not found. Please install Piper first.'}), 500
                
                # Run Piper TTS
                result = subprocess.run([
                    piper_cmd,
                    '--model', str(voice_model),
                    '--output_file', temp_path
                ], input=preview_text, text=True, capture_output=True, timeout=30)
                
                if result.returncode == 0:
                    file_size = os.path.getsize(temp_path)
                    
                    # Try to play the audio
                    play_success = False
                    try:
                        play_result = subprocess.run(['aplay', temp_path], 
                                                   capture_output=True, timeout=10)
                        play_success = play_result.returncode == 0
                    except:
                        pass
                    
                    return jsonify({
                        'success': True,
                        'message': f'Voice preview generated ({file_size} bytes)',
                        'voice_name': voice_name,
                        'played': play_success,
                        'audio_file_size': file_size
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Piper TTS failed: {result.stderr}'
                    }), 500
                    
            finally:
                # Clean up
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            current_app.logger.error(f"Voice preview API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/piper/set-voice', methods=['POST'])
    def set_piper_voice():
        """Set the current Piper TTS voice."""
        try:
            data = request.get_json()
            if not data or 'voice_name' not in data:
                return jsonify({'success': False, 'error': 'Voice name required'}), 400
            
            voice_name = data['voice_name']
            
            # Update voice control if available
            if hasattr(current_app.service_manager, 'voice_control') and current_app.service_manager.voice_control:
                voice_control = current_app.service_manager.voice_control
                
                # Check if voice control uses Piper TTS
                if hasattr(voice_control, 'piper_model'):
                    voice_control.piper_model = f"{voice_name}.onnx"
                    
                # Update environment variable for persistence
                os.environ['PIPER_VOICE_MODEL'] = f"{voice_name}.onnx"
                
                # Update .env file if it exists
                try:
                    env_file = Path('.env')
                    if env_file.exists():
                        lines = []
                        voice_updated = False
                        
                        with open(env_file, 'r') as f:
                            for line in f:
                                if line.startswith('PIPER_VOICE_MODEL='):
                                    lines.append(f'PIPER_VOICE_MODEL={voice_name}.onnx\n')
                                    voice_updated = True
                                else:
                                    lines.append(line)
                        
                        if not voice_updated:
                            lines.append(f'PIPER_VOICE_MODEL={voice_name}.onnx\n')
                        
                        with open(env_file, 'w') as f:
                            f.writelines(lines)
                except Exception as e:
                    current_app.logger.warning(f"Could not update .env file: {e}")
                
                return jsonify({
                    'success': True,
                    'message': f'Voice set to {_format_voice_name(voice_name)}',
                    'voice_name': voice_name
                })
            else:
                return jsonify({'success': False, 'error': 'Voice control not available'}), 500
                
        except Exception as e:
            current_app.logger.error(f"Set voice API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def _format_voice_name(voice_name):
        """Format voice name for display."""
        # Convert en_US-amy-medium to "Amy (US, Medium)"
        parts = voice_name.split('-')
        if len(parts) >= 3:
            lang = parts[0]
            name = parts[1].title()
            quality = parts[2].title()
            
            lang_map = {
                'en_US': 'US English',
                'en_UK': 'UK English',
                'en_GB': 'British English'
            }
            
            lang_display = lang_map.get(lang, lang)
            return f"{name} ({lang_display}, {quality})"
        
        return voice_name.replace('_', ' ').replace('-', ' ').title()
    
    def _get_current_piper_voice():
        """Get the currently selected Piper voice."""
        try:
            # Check voice control first
            if hasattr(current_app.service_manager, 'voice_control') and current_app.service_manager.voice_control:
                voice_control = current_app.service_manager.voice_control
                if hasattr(voice_control, 'piper_model'):
                    return voice_control.piper_model.replace('.onnx', '')
            
            # Check environment variable
            current_voice = os.getenv('PIPER_VOICE_MODEL', 'en_US-amy-medium.onnx')
            return current_voice.replace('.onnx', '')
            
        except:
            return 'en_US-amy-medium'
    
    # === Audio API Endpoints ===
    
    @app.route('/api/audio/devices', methods=['GET'])
    def get_audio_devices():
        """Get available audio devices."""
        try:
            import subprocess
            
            # Get playback devices
            playback_result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
            playback_devices = []
            if playback_result.returncode == 0:
                for line in playback_result.stdout.split('\n'):
                    if 'card' in line and ':' in line:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            card_info = parts[0].strip()
                            device_name = parts[1].strip()
                            card_num = card_info.split()[1]
                            playback_devices.append({
                                'card': card_num,
                                'name': device_name
                            })
            
            # Get recording devices
            recording_result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
            recording_devices = []
            if recording_result.returncode == 0:
                for line in recording_result.stdout.split('\n'):
                    if 'card' in line and ':' in line:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            card_info = parts[0].strip()
                            device_name = parts[1].strip()
                            card_num = card_info.split()[1]
                            recording_devices.append({
                                'card': card_num,
                                'name': device_name
                            })
            
            return jsonify({
                'success': True,
                'data': {
                    'playback': playback_devices,
                    'recording': recording_devices
                }
            })
        except Exception as e:
            current_app.logger.error(f"Audio devices API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/audio/test-microphone', methods=['POST'])
    def test_microphone():
        """Test microphone by recording 5 seconds of audio."""
        try:
            import subprocess
            import tempfile
            import os
            
            # Create temporary file for recording
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                # Record 5 seconds of audio
                result = subprocess.run([
                    'arecord', '-f', 'cd', '-t', 'wav', '-d', '5', temp_path
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    # Check if file was created and has content
                    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 1000:
                        # Get basic volume info (file size as rough indicator)
                        file_size = os.path.getsize(temp_path)
                        volume_level = "Good" if file_size > 50000 else "Low" if file_size > 10000 else "Very Low"
                        
                        return jsonify({
                            'success': True,
                            'message': 'Microphone test successful',
                            'volume_level': volume_level,
                            'file_size': file_size
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'error': 'No audio recorded - check microphone connection'
                        })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Recording failed: {result.stderr}'
                    })
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except subprocess.TimeoutExpired:
            return jsonify({
                'success': False,
                'error': 'Recording timeout - microphone may not be working'
            })
        except Exception as e:
            current_app.logger.error(f"Microphone test API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/audio/test-speakers', methods=['POST'])
    def test_speakers():
        """Test speakers using speaker-test command."""
        try:
            import subprocess
            
            # Run speaker test for 2 seconds
            result = subprocess.run([
                'timeout', '2', 'speaker-test', '-c', '2', '-r', '44100', '-t', 'sine'
            ], capture_output=True, text=True)
            
            # speaker-test returns non-zero when interrupted by timeout, which is expected
            if 'ALSA' in result.stderr or 'Front Left' in result.stdout:
                return jsonify({
                    'success': True,
                    'message': 'Speaker test completed'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Speaker test failed - check speaker connection'
                })
                
        except Exception as e:
            current_app.logger.error(f"Speaker test API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/audio/play-test-sound', methods=['POST'])
    def play_test_sound():
        """Play a test sound using text-to-speech."""
        try:
            # Use voice control to play test sound if available
            voice_control = getattr(current_app.service_manager, 'voice_control', None)
            if voice_control and hasattr(voice_control, 'speak'):
                voice_control.speak("Audio test successful. Speakers are working properly.")
                return jsonify({
                    'success': True,
                    'message': 'Test sound played successfully'
                })
            else:
                # Fallback to system beep
                import subprocess
                result = subprocess.run(['beep'], capture_output=True)
                return jsonify({
                    'success': True,
                    'message': 'System beep played (TTS not available)'
                })
                
        except Exception as e:
            current_app.logger.error(f"Play test sound API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/audio/volume', methods=['POST'])
    def update_audio_volume():
        """Update microphone and speaker volume levels."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            import subprocess
            results = []
            
            # Update speaker volume if provided
            if 'speaker_volume' in data:
                volume = max(0, min(100, int(data['speaker_volume'])))
                volume_set = False
                
                # Try different USB audio cards and control names
                for card in ['1', '2', '0']:  # Try common USB audio card numbers
                    if volume_set:
                        break
                    for control in ['Speaker', 'PCM', 'Master', 'Headphone', 'Front', 'USB Audio']:
                        try:
                            result = subprocess.run([
                                'amixer', '-c', card, 'set', control, f'{volume}%'
                            ], capture_output=True, text=True, timeout=5)
                            if result.returncode == 0:
                                results.append(f"Speaker volume set to {volume}% (Card {card}, {control})")
                                volume_set = True
                                break
                        except:
                            continue
                
                if not volume_set:
                    results.append(f"Could not set speaker volume - no compatible audio controls found")
            
            # Update microphone volume if provided
            if 'mic_volume' in data:
                volume = max(0, min(100, int(data['mic_volume'])))
                volume_set = False
                
                # Try different USB audio cards and control names
                for card in ['1', '2', '0']:  # Try common USB audio card numbers
                    if volume_set:
                        break
                    for control in ['Mic', 'Capture', 'Front Mic', 'Rear Mic', 'USB Audio Mic']:
                        try:
                            result = subprocess.run([
                                'amixer', '-c', card, 'set', control, f'{volume}%'
                            ], capture_output=True, text=True, timeout=5)
                            if result.returncode == 0:
                                results.append(f"Microphone volume set to {volume}% (Card {card}, {control})")
                                volume_set = True
                                break
                        except:
                            continue
                
                if not volume_set:
                    results.append(f"Could not set microphone volume - no compatible audio controls found")
            
            # Track volume changes
            if results:
                _track_activity("Volume adjusted", '; '.join(results))
            
            return jsonify({
                'success': True,
                'message': '; '.join(results) if results else 'No volume changes applied'
            })
            
        except Exception as e:
            current_app.logger.error(f"Audio volume API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/activities', methods=['GET'])
    def get_recent_activities():
        """Get recent activity log."""
        try:
            # Limit to last 50 activities
            recent = current_app.recent_activities[-50:] if len(current_app.recent_activities) > 50 else current_app.recent_activities
            return jsonify({'success': True, 'data': recent})
        except Exception as e:
            current_app.logger.error(f"Activities API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/health')
    def health_check():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0'
        })
    
    def _get_uptime():
        """Get system uptime."""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                return str(timedelta(seconds=int(uptime_seconds)))
        except:
            return "Unknown"
    
    def _get_cpu_temperature():
        """Get CPU temperature."""
        try:
            # Try Raspberry Pi thermal zone first
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_millidegrees = int(f.read().strip())
                temp_celsius = temp_millidegrees / 1000.0
                return round(temp_celsius, 1)
        except:
            try:
                # Try alternative thermal zones
                import glob
                thermal_files = glob.glob('/sys/class/thermal/thermal_zone*/temp')
                if thermal_files:
                    with open(thermal_files[0], 'r') as f:
                        temp_millidegrees = int(f.read().strip())
                        temp_celsius = temp_millidegrees / 1000.0
                        return round(temp_celsius, 1)
            except:
                pass
            
            # Simulation mode - return simulated temperature
            import random
            simulation_mode = os.getenv('SIMULATION_MODE', 'false').lower() == 'true'
            if simulation_mode:
                # Return a realistic simulated temperature
                return round(45.0 + random.uniform(-5, 10), 1)
            
            return None
    
    def _get_system_health_status():
        """Get overall system health status."""
        try:
            # Check various system metrics
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            cpu_temp = _get_cpu_temperature()
            
            issues = []
            
            # Check CPU usage
            if cpu_percent > 90:
                issues.append("High CPU usage")
            
            # Check memory usage
            if memory_percent > 85:
                issues.append("High memory usage")
            
            # Check disk usage
            if disk_percent > 90:
                issues.append("Low disk space")
            
            # Check temperature
            if cpu_temp and cpu_temp > 80:
                issues.append("High CPU temperature")
            
            # Check if display manager is responding
            if not hasattr(current_app.display_manager, 'last_image_hash'):
                issues.append("Display manager not responding")
            
            # Check API connectivity
            try:
                test_verse = current_app.verse_manager.get_current_verse()
                if not test_verse or 'error' in test_verse:
                    issues.append("Bible API connectivity issues")
            except Exception:
                issues.append("Bible API connectivity issues")
            
            # Check free disk space (warn earlier)
            if disk_percent > 85:
                issues.append("Low disk space warning")
            
            # Check if voice control is functioning (if enabled)
            if hasattr(current_app.service_manager, 'voice_control') and current_app.service_manager.voice_control:
                try:
                    voice_status = current_app.service_manager.voice_control.get_voice_status()
                    if not voice_status.get('enabled', False):
                        issues.append("Voice control disabled")
                except Exception:
                    issues.append("Voice control not responding")
            
            # Check for scheduler conflicts
            import subprocess
            try:
                result = subprocess.run(['pgrep', '-f', 'bible.*clock'], capture_output=True, text=True)
                processes = result.stdout.strip().split('\n') if result.stdout.strip() else []
                if len(processes) > 3:  # Main process, health monitor, and one extra allowed
                    issues.append("Multiple scheduler processes detected")
            except:
                pass
            
            # Check display update frequency (should update regularly)
            if hasattr(current_app.display_manager, 'last_update_time'):
                from datetime import datetime, timedelta
                if datetime.now() - getattr(current_app.display_manager, 'last_update_time', datetime.now()) > timedelta(minutes=10):
                    issues.append("Display updates stalled")
            
            # Return status with more granular levels
            if not issues:
                return "excellent"  # No issues at all
            elif len(issues) == 1 and any(x in issues[0] for x in ["Voice control", "warning"]):
                return "good"  # Minor non-critical issues
            elif len(issues) <= 2:
                return "warning"  # Some issues but functioning
            else:
                return "critical"  # Multiple serious issues
                
        except Exception:
            return "unknown"
    
    def _get_accurate_verses_today():
        """Get accurate verse count from daily metrics file."""
        try:
            from datetime import datetime
            import json
            
            today = datetime.now().strftime('%Y-%m-%d')
            daily_file = Path('data/daily_metrics.json')
            
            if daily_file.exists():
                with open(daily_file, 'r') as f:
                    daily_data = json.load(f)
                
                today_data = daily_data.get(today, {})
                return today_data.get('verses_displayed_today', 0)
            
            # Fallback to in-memory count if file not available
            return getattr(current_app.verse_manager, 'statistics', {}).get('verses_today', 0)
        except Exception:
            return 0
    
    def _get_health_details():
        """Get detailed health information."""
        try:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu_temp = _get_cpu_temperature()
            
            details = {
                "purpose": "System health monitoring helps ensure optimal Bible Clock performance",
                "health_status_levels": {
                    "excellent": "No issues detected - system running optimally",
                    "good": "Minor non-critical issues - system functioning well",
                    "warning": "Some issues detected - system functioning but may need attention",
                    "critical": "Multiple serious issues - immediate attention recommended",
                    "unknown": "Unable to determine system status"
                },
                "metrics": {
                    "cpu": {
                        "value": cpu_percent,
                        "status": "good" if cpu_percent < 70 else "warning" if cpu_percent < 90 else "critical",
                        "description": "CPU usage percentage - lower is better for smooth operation"
                    },
                    "memory": {
                        "value": memory.percent,
                        "status": "good" if memory.percent < 70 else "warning" if memory.percent < 85 else "critical",
                        "description": "RAM usage percentage - high usage can cause performance issues"
                    },
                    "disk": {
                        "value": disk.percent,
                        "status": "good" if disk.percent < 80 else "warning" if disk.percent < 90 else "critical",
                        "description": "Storage usage percentage - low space can prevent updates and logging"
                    },
                    "temperature": {
                        "value": cpu_temp,
                        "status": "good" if (cpu_temp and cpu_temp < 65) else "warning" if (cpu_temp and cpu_temp < 80) else "critical",
                        "description": "CPU temperature in Celsius - high temps can cause system instability"
                    },
                    "api_connectivity": {
                        "value": _check_api_connectivity(),
                        "status": "good" if _check_api_connectivity() else "critical",
                        "description": "Bible API connectivity - essential for verse retrieval"
                    },
                    "voice_control": {
                        "value": _check_voice_control_status(),
                        "status": "good" if _check_voice_control_status() == "active" else "warning" if _check_voice_control_status() == "disabled" else "critical",
                        "description": "Voice control system status - enables voice commands and AI features"
                    }
                },
                "uptime": _get_uptime(),
                "last_updated": datetime.now().isoformat(),
                "recommendations": _get_health_recommendations(cpu_percent, memory.percent, disk.percent, cpu_temp)
            }
            
            return details
            
        except Exception as e:
            return {"error": str(e), "purpose": "System health monitoring helps ensure optimal performance"}
    
    def _get_health_recommendations(cpu_percent, memory_percent, disk_percent, cpu_temp):
        """Get health recommendations based on current metrics."""
        recommendations = []
        
        if cpu_percent > 80:
            recommendations.append("Consider reducing background processes or upgrading hardware")
        
        if memory_percent > 80:
            recommendations.append("Free up memory by closing unused applications or restarting the system")
        
        if disk_percent > 85:
            recommendations.append("Clean up old files, logs, or consider expanding storage")
        
        if cpu_temp and cpu_temp > 75:
            recommendations.append("Improve cooling or reduce system load to prevent overheating")
        
        if not recommendations:
            recommendations.append("System is running optimally - no action needed")
        
        return recommendations
    
    def _check_api_connectivity():
        """Check if Bible API is accessible."""
        try:
            # Quick test of verse retrieval
            test_verse = current_app.verse_manager.get_current_verse()
            return bool(test_verse and 'error' not in test_verse and test_verse.get('text'))
        except Exception:
            return False
    
    def _check_voice_control_status():
        """Check voice control system status."""
        try:
            if hasattr(current_app.service_manager, 'voice_control') and current_app.service_manager.voice_control:
                voice_status = current_app.service_manager.voice_control.get_voice_status()
                if voice_status.get('enabled', False):
                    return "active"
                else:
                    return "disabled"
            return "not_available"
        except Exception:
            return "error"
    
    def _generate_basic_statistics():
        """Generate basic statistics."""
        return {
            'verses_displayed_today': 1440,  # Minutes in a day
            'most_common_book': 'Psalms',
            'total_uptime': _get_uptime(),
            'api_success_rate': 98.5,
            'average_response_time': 0.85
        }
    
    @app.route('/api/translation-completion', methods=['GET'])
    def translation_completion():
        """Get completion statistics for all Bible translations."""
        try:
            if hasattr(current_app.verse_manager, 'translation_completion'):
                completion = current_app.verse_manager.translation_completion
                total_verses = current_app.verse_manager._get_total_bible_verses() if hasattr(current_app.verse_manager, '_get_total_bible_verses') else 31100
                
                # Calculate detailed stats
                detailed_stats = {}
                for translation, percentage in completion.items():
                    cached_verses = int((percentage / 100.0) * total_verses)
                    detailed_stats[translation] = {
                        'completion_percentage': percentage,
                        'cached_verses': cached_verses,
                        'total_verses': total_verses,
                        'display_name': current_app.verse_manager.get_translation_display_names().get(translation, translation.upper())
                    }
                
                # Get daily cache count
                daily_cached = 0
                if hasattr(current_app.verse_manager, 'statistics') and 'verses_cached_today' in current_app.verse_manager.statistics:
                    daily_cached = current_app.verse_manager.statistics['verses_cached_today']
                
                return jsonify({
                    'success': True, 
                    'data': {
                        'translations': detailed_stats,
                        'summary': {
                            'total_translations': len(completion),
                            'completed_translations': len([t for t, p in completion.items() if p >= 100.0]),
                            'total_bible_verses': total_verses,
                            'overall_progress': current_app.verse_manager._format_completion_summary() if hasattr(current_app.verse_manager, '_format_completion_summary') else 'Not available',
                            'verses_cached_today': daily_cached
                        }
                    }
                })
            else:
                return jsonify({'success': True, 'data': {
                    'translations': {},
                    'summary': {
                        'total_translations': 0,
                        'completed_translations': 0,
                        'total_bible_verses': 31100,
                        'overall_progress': 'Translation caching not available',
                        'verses_cached_today': 0
                    }
                }})
        except Exception as e:
            current_app.logger.error(f"Translation completion API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # Legacy endpoint for backward compatibility
    @app.route('/api/amp-completion', methods=['GET'])
    def amp_completion():
        """Get AMP Bible completion statistics (legacy endpoint)."""
        try:
            response = translation_completion()
            data = response.get_json()
            
            if data.get('success') and 'amp' in data['data']['translations']:
                amp_stats = data['data']['translations']['amp']
                return jsonify({'success': True, 'data': amp_stats})
            else:
                return jsonify({'success': True, 'data': {
                    'completion_percentage': 0.0,
                    'cached_verses': 0,
                    'total_verses': 31100,
                    'message': 'AMP completion tracking not available'
                }})
        except Exception as e:
            current_app.logger.error(f"AMP completion API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # === Mobile-specific API Endpoints ===
    
    @app.route('/api/test-mobile', methods=['GET'])
    def test_mobile():
        return jsonify({'success': True, 'message': 'Mobile endpoints working'})
    
    @app.route('/api/voice/wake-word', methods=['POST'])
    def toggle_wake_word():
        """Toggle voice wake word detection for mobile."""
        try:
            if not hasattr(current_app.service_manager, 'voice_control') or not current_app.service_manager.voice_control:
                return jsonify({'success': False, 'error': 'Voice control not available'})
            
            data = request.get_json()
            enabled = data.get('enabled', False)
            
            # Toggle voice control enabled state
            current_app.service_manager.voice_control.enabled = enabled
            
            # Also set listening state to match enabled state
            current_app.service_manager.voice_control.listening = enabled
            
            # Actually start or stop the voice control service
            if enabled:
                if hasattr(current_app.service_manager.voice_control, 'start_listening'):
                    current_app.service_manager.voice_control.start_listening()
                    current_app.logger.info("Voice control service started")
                else:
                    current_app.logger.warning("Voice control start_listening method not available")
            else:
                if hasattr(current_app.service_manager.voice_control, 'stop_listening'):
                    current_app.service_manager.voice_control.stop_listening()
                    current_app.logger.info("Voice control service stopped")
                else:
                    current_app.logger.warning("Voice control stop_listening method not available")
            
            # Update environment variable for persistence
            os.environ['ENABLE_VOICE'] = 'true' if enabled else 'false'
            
            message = f'Voice control {"enabled" if enabled else "disabled"} - service {"started" if enabled else "stopped"}'
            return jsonify({'success': True, 'message': message})
            
        except Exception as e:
            current_app.logger.error(f"Wake word toggle API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/voice-control/volume', methods=['GET', 'POST'])
    def voice_volume_control():
        """Get or set voice control volume."""
        try:
            if not hasattr(current_app.service_manager, 'voice_control') or not current_app.service_manager.voice_control:
                return jsonify({'success': False, 'error': 'Voice control not available'})
            
            if request.method == 'GET':
                # Get current volume
                volume = getattr(current_app.service_manager.voice_control, 'volume', 70)
                return jsonify({'volume': volume})
            
            elif request.method == 'POST':
                # Set volume
                data = request.get_json()
                if not data or 'volume' not in data:
                    return jsonify({'success': False, 'error': 'Volume value required'})
                
                volume = int(data['volume'])
                if volume < 0 or volume > 100:
                    return jsonify({'success': False, 'error': 'Volume must be between 0 and 100'})
                
                # Set volume on voice control
                if hasattr(current_app.service_manager.voice_control, 'set_volume'):
                    current_app.service_manager.voice_control.set_volume(volume)
                else:
                    # Store volume directly if set_volume method not available
                    current_app.service_manager.voice_control.volume = volume
                
                current_app.logger.info(f"Voice control volume set to: {volume}%")
                return jsonify({'success': True, 'volume': volume})
                
        except Exception as e:
            current_app.logger.error(f"Voice volume control API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def _apply_display_transformations(image):
        """Apply transformations to show what the final display looks like after hardware processing."""
        try:
            from PIL import Image as PILImage
            import logging
            
            logger = logging.getLogger(__name__)
            
            # Create a copy to avoid modifying the original
            transformed_image = image.copy()
            
            # The image generation creates a "raw" image, but the hardware applies transformations
            # To show what users actually see, we need to apply the REVERSE of hardware transformations
            # Hardware: mirror=true, rotation=180
            # So preview should show: rotation=180 first, then reverse mirror
            
            # Step 1: Apply software rotation (same as hardware)
            rotation_setting = os.getenv('DISPLAY_PHYSICAL_ROTATION', '180')
            logger.info(f"Preview transformation - Rotation setting: {rotation_setting}")
            
            if rotation_setting == '180':
                transformed_image = transformed_image.rotate(180)
                logger.info("Applied 180-degree rotation to preview")
            
            # Step 2: Do NOT apply mirroring - the raw image is already correct for reading
            # Hardware mirroring corrects the display, so preview should show the corrected result
            mirror_setting = os.getenv('DISPLAY_MIRROR', 'false').lower()
            logger.info(f"Preview transformation - Mirror setting: {mirror_setting} (not applied to preview)")
            
            return transformed_image
            
        except Exception as e:
            # If transformation fails, return original image
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Preview transformation error: {e}")
            return image

    def _cleanup_old_preview_images():
        """Clean up old preview images to prevent accumulation."""
        try:
            import time
            import os
            from pathlib import Path
            
            static_dir = Path('src/web_interface/static')
            if not static_dir.exists():
                return
            
            # Clean up preview images older than 1 hour
            current_time = time.time()
            max_age = 3600  # 1 hour in seconds
            
            for preview_file in static_dir.glob('preview*.png'):
                if preview_file.exists():
                    file_age = current_time - preview_file.stat().st_mtime
                    if file_age > max_age:
                        preview_file.unlink()
                        print(f"Cleaned up old preview image: {preview_file.name}")
            
            # Also clean up any temporary image files
            for temp_file in static_dir.glob('temp_*.png'):
                if temp_file.exists():
                    file_age = current_time - temp_file.stat().st_mtime
                    if file_age > max_age:
                        temp_file.unlink()
                        print(f"Cleaned up temp image: {temp_file.name}")
                        
        except Exception as e:
            print(f"Preview cleanup error: {e}")
    
    @app.route('/api/weather/settings', methods=['GET'])
    def get_weather_settings():
        """Get weather settings."""
        try:
            from weather_settings import weather_settings
            return jsonify({
                'success': True,
                'data': weather_settings.get_all_settings()
            })
        except Exception as e:
            current_app.logger.error(f"Weather settings API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/weather/settings', methods=['POST'])
    def update_weather_settings():
        """Update weather settings."""
        try:
            from weather_settings import weather_settings
            
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            # Update settings
            weather_settings.update_settings(data)
            
            return jsonify({
                'success': True,
                'message': 'Weather settings updated successfully'
            })
        except Exception as e:
            current_app.logger.error(f"Weather settings update error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/error-log', methods=['GET'])
    def get_error_log():
        """Get daily error log data."""
        try:
            error_stats = error_log_manager.get_error_stats()
            return jsonify({
                'success': True,
                'data': error_stats
            })
        except Exception as e:
            current_app.logger.error(f"Error log API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/error-log', methods=['DELETE'])
    def clear_error_log():
        """Clear daily error log."""
        try:
            error_log_manager.clear_errors()
            return jsonify({
                'success': True,
                'message': 'Error log cleared successfully'
            })
        except Exception as e:
            current_app.logger.error(f"Error log clear error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/devotional/interval', methods=['POST'])
    def set_devotional_interval():
        """Set devotional mode rotation interval."""
        try:
            data = request.get_json()
            if not data or 'interval' not in data:
                return jsonify({'success': False, 'error': 'Interval value required'}), 400
            
            interval = int(data['interval'])
            if interval < 1 or interval > 120:
                return jsonify({'success': False, 'error': 'Interval must be between 1 and 120 minutes'}), 400
            
            # Update devotional manager interval
            if hasattr(current_app, 'devotional_manager') and current_app.devotional_manager:
                current_app.devotional_manager.rotation_minutes = interval
                current_app.logger.info(f"Devotional interval set to: {interval} minutes")
                return jsonify({'success': True, 'interval': interval})
            else:
                return jsonify({'success': False, 'error': 'Devotional manager not available'}), 500
                
        except Exception as e:
            current_app.logger.error(f"Devotional interval API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/random/interval', methods=['POST'])
    def set_random_interval():
        """Set random mode rotation interval."""
        try:
            data = request.get_json()
            if not data or 'interval' not in data:
                return jsonify({'success': False, 'error': 'Interval value required'}), 400
            
            interval = int(data['interval'])
            if interval < 1 or interval > 60:
                return jsonify({'success': False, 'error': 'Interval must be between 1 and 60 minutes'}), 400
            
            # Store random interval in verse manager or environment
            os.environ['RANDOM_INTERVAL_MINUTES'] = str(interval)
            current_app.logger.info(f"Random mode interval set to: {interval} minutes")
            return jsonify({'success': True, 'interval': interval})
                
        except Exception as e:
            current_app.logger.error(f"Random interval API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/date/interval', methods=['POST'])
    def set_date_interval():
        """Set Bible events mode rotation interval."""
        try:
            data = request.get_json()
            if not data or 'interval' not in data:
                return jsonify({'success': False, 'error': 'Interval value required'}), 400
            
            interval = int(data['interval'])
            if interval < 1 or interval > 30:
                return jsonify({'success': False, 'error': 'Interval must be between 1 and 30 minutes'}), 400
            
            # Store date interval in environment for verse manager
            os.environ['DATE_INTERVAL_MINUTES'] = str(interval)
            current_app.logger.info(f"Bible events interval set to: {interval} minutes")
            return jsonify({'success': True, 'interval': interval})
                
        except Exception as e:
            current_app.logger.error(f"Date interval API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/default-mode', methods=['GET', 'POST'])
    def default_mode_api():
        """Get or set the default display mode for startup."""
        try:
            if request.method == 'GET':
                # Get current default mode
                current_mode = os.getenv('DEFAULT_DISPLAY_MODE', 'time').lower()
                return jsonify({'success': True, 'mode': current_mode})
            
            elif request.method == 'POST':
                # Set default mode
                data = request.get_json()
                if not data or 'mode' not in data:
                    return jsonify({'success': False, 'error': 'Mode value required'}), 400
                
                mode = data['mode'].lower()
                valid_modes = ['time', 'parallel', 'devotional', 'random', 'date', 'weather', 'news']
                
                if mode not in valid_modes:
                    return jsonify({'success': False, 'error': f'Invalid mode. Valid modes: {", ".join(valid_modes)}'}), 400
                
                # Store default mode in environment variable for persistence
                os.environ['DEFAULT_DISPLAY_MODE'] = mode
                current_app.logger.info(f"Default display mode set to: {mode}")
                
                return jsonify({'success': True, 'mode': mode})
                
        except Exception as e:
            current_app.logger.error(f"Default mode API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/text-query', methods=['POST'])
    def process_text_query():
        """Process text-based AI questions and display on screen."""
        try:
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify({'success': False, 'error': 'No query provided'}), 400
            
            query = data['query'].strip()
            force_visual = data.get('force_visual', True)
            
            if not query:
                return jsonify({'success': False, 'error': 'Query cannot be empty'}), 400
            
            if len(query) > 500:
                return jsonify({'success': False, 'error': 'Query too long (max 500 characters)'}), 400
            
            # Check if ChatGPT is available
            if not hasattr(current_app.service_manager, 'voice_control') or not current_app.service_manager.voice_control:
                return jsonify({'success': False, 'error': 'AI service not available'}), 503
            
            # Use the existing voice control ChatGPT integration
            voice_control = current_app.service_manager.voice_control
            
            # Check if ChatGPT is enabled
            chatgpt_enabled = voice_control.chatgpt_enabled
                
            if not chatgpt_enabled:
                return jsonify({'success': False, 'error': 'ChatGPT is not enabled. Please enable it in voice settings.'}), 400
            
            try:
                current_app.logger.info(f"Processing text query: {query[:100]}...")
                
                # Use the voice control's ChatGPT integration directly
                response = None
                if hasattr(voice_control, 'query_chatgpt'):
                    response = voice_control.query_chatgpt(query)
                elif hasattr(voice_control, 'ask_chatgpt'):
                    response = voice_control.ask_chatgpt(query)
                else:
                    # Fallback: try to call ChatGPT directly if available
                    if hasattr(voice_control, 'openai_client') and voice_control.openai_client:
                        import os
                        system_prompt = os.getenv('CHATGPT_SYSTEM_PROMPT', 
                            'You are a knowledgeable biblical scholar and theologian helping users understand Bible verses, biblical history, theology, and Christian faith. Keep responses concise but meaningful, suitable for voice interaction.')
                        
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": query}
                        ]
                        
                        completion = voice_control.openai_client.chat.completions.create(
                            model=voice_control.chatgpt_model or "gpt-3.5-turbo",
                            messages=messages,
                            max_tokens=int(os.getenv('CHATGPT_MAX_TOKENS', '150')),
                            temperature=float(os.getenv('CHATGPT_TEMPERATURE', '0.7'))
                        )
                        response = completion.choices[0].message.content.strip()
                
                if response:
                    # Display the response on the e-ink screen
                    if hasattr(current_app.service_manager, 'display_manager'):
                        try:
                            current_app.service_manager.display_manager.show_transient_message(
                                "ai_response_page", response, duration=15.0
                            )
                            current_app.logger.info(f"Text query response displayed: {response[:100]}...")
                        except Exception as display_error:
                            current_app.logger.error(f"Display error: {display_error}")
                            # Don't fail the whole request if display fails
                    
                    current_app.logger.info(f"Text query completed successfully")
                    return jsonify({
                        'success': True, 
                        'message': 'Question processed and displayed on screen',
                        'response_preview': response[:100] + '...' if len(response) > 100 else response
                    })
                else:
                    return jsonify({'success': False, 'error': 'No response received from ChatGPT'})
                
            except Exception as chatgpt_error:
                current_app.logger.error(f"ChatGPT processing failed: {chatgpt_error}")
                return jsonify({'success': False, 'error': f'AI processing failed: {str(chatgpt_error)}'})
            
        except Exception as e:
            logger.error(f"Text query processing error: {e}")
            return jsonify({'success': False, 'error': f'Server error: {str(e)}'})
    
    @app.route('/api/bible-clock-metrics', methods=['GET'])
    def get_bible_clock_metrics():
        """Get real-time Bible Clock metrics according to requirements."""
        try:
            period = request.args.get('period', 'today')  # today, week, month, year, alltime
            
            # Get aggregated metrics for the period
            metrics = current_app.bible_metrics.get_aggregated_metrics(period)
            
            return jsonify({
                'success': True,
                'data': metrics
            })
        except Exception as e:
            current_app.logger.error(f"Bible Clock metrics API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bible-clock-metrics/current', methods=['GET'])
    def get_current_bible_clock_metrics():
        """Get current real-time snapshot of Bible Clock metrics."""
        try:
            # Get current snapshot
            snapshot = current_app.bible_metrics.get_current_metrics()
            
            return jsonify({
                'success': True,
                'data': {
                    'verses_displayed_today': snapshot.verses_displayed_today,
                    'uptime_hours': round(snapshot.uptime_hours, 1),
                    'mode_usage_hours': {
                        mode: round(seconds / 3600.0, 1) 
                        for mode, seconds in snapshot.mode_usage_seconds.items()
                    },
                    'translation_usage_count': snapshot.translation_usage_count,
                    'bible_books_accessed_count': len(snapshot.bible_books_accessed),
                    'bible_books_accessed': snapshot.bible_books_accessed,
                    'recent_activities': snapshot.recent_activities,
                    'translation_completion_percentages': snapshot.translation_completion_percentages,
                    'timestamp': snapshot.timestamp
                }
            })
        except Exception as e:
            current_app.logger.error(f"Current Bible Clock metrics API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # Display Schedule API Endpoints
    @app.route('/api/display-schedule', methods=['GET'])
    def get_display_schedule():
        """Get current display schedule configuration."""
        try:
            if not current_app.display_schedule_manager:
                return jsonify({'success': False, 'error': 'Display schedule not available'}), 404
                
            schedule_data = current_app.display_schedule_manager.get_schedule()
            return jsonify({
                'success': True,
                'data': schedule_data
            })
        except Exception as e:
            current_app.logger.error(f"Get display schedule error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/display-schedule', methods=['POST'])
    def update_display_schedule():
        """Update display schedule configuration."""
        try:
            if not current_app.display_schedule_manager:
                return jsonify({'success': False, 'error': 'Display schedule not available'}), 404
                
            data = request.json
            if not data or 'schedule' not in data:
                return jsonify({'success': False, 'error': 'Invalid request data'}), 400
                
            success = current_app.display_schedule_manager.update_schedule(data['schedule'])
            if success:
                return jsonify({'success': True, 'message': 'Schedule updated successfully'})
            else:
                return jsonify({'success': False, 'error': 'Failed to update schedule'}), 500
                
        except Exception as e:
            current_app.logger.error(f"Update display schedule error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/display-schedule/status', methods=['GET'])
    def get_display_schedule_status():
        """Get current display schedule status."""
        try:
            if not current_app.display_schedule_manager:
                return jsonify({'success': False, 'error': 'Display schedule not available'}), 404
                
            from datetime import datetime
            now = datetime.now()
            schedule_info = current_app.display_schedule_manager.get_schedule()
            next_event = current_app.display_schedule_manager.get_next_schedule_event()
            
            return jsonify({
                'success': True,
                'data': {
                    'current_status': schedule_info.get('current_status', {}),
                    'next_event': next_event,
                    'current_time': now.isoformat(),
                    'schedule': schedule_info
                }
            })
        except Exception as e:
            current_app.logger.error(f"Get display schedule status error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/display-schedule/control', methods=['POST'])
    def control_display_schedule():
        """Manual control for display on/off."""
        try:
            if not current_app.display_schedule_manager:
                return jsonify({'success': False, 'error': 'Display schedule not available'}), 404
                
            data = request.json
            if not data or 'action' not in data:
                return jsonify({'success': False, 'error': 'Invalid request data'}), 400
                
            action = data['action']
            if action == 'turn_on':
                current_app.display_schedule_manager.turn_display_on(scheduled=False)
                return jsonify({'success': True, 'message': 'Display turned on manually'})
            elif action == 'turn_off':
                current_app.display_schedule_manager.turn_display_off(scheduled=False)
                return jsonify({'success': True, 'message': 'Display turned off manually'})
            else:
                return jsonify({'success': False, 'error': 'Invalid action'}), 400
                
        except Exception as e:
            current_app.logger.error(f"Display schedule control error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    return app
