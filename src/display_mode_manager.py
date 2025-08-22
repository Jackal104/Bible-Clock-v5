"""
Display Mode Manager - Handles per-mode settings and default mode selection.
Each display mode can have independent backgrounds, borders, fonts, and other settings.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional


class DisplayModeManager:
    """Manages display mode settings and customization."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.settings_file = Path('data/display_mode_settings.json')
        self.settings = self._load_settings()
        
    def _load_settings(self) -> Dict[str, Any]:
        """Load display mode settings from file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                self.logger.info("Display mode settings loaded")
                return settings
            except Exception as e:
                self.logger.error(f"Error loading display mode settings: {e}")
        
        # Default settings if file doesn't exist or fails to load
        return self._get_default_settings()
    
    def _save_settings(self):
        """Save display mode settings to file."""
        try:
            self.settings_file.parent.mkdir(exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            self.logger.info("Display mode settings saved")
        except Exception as e:
            self.logger.error(f"Error saving display mode settings: {e}")
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default display mode settings."""
        return {
            "default_mode": "time",
            "mode_settings": {
                "time": {
                    "name": "Time Mode",
                    "description": "HH:MM = Chapter:Verse",
                    "background_index": 0,
                    "border_index": 0,
                    "font_name": "default",
                    "verse_font_size": 80,
                    "reference_font_size": 84,
                    "title_font_size": 48,
                    "display_scale": 1.0,
                    "parallel_mode": False,
                    "primary_translation": "kjv",
                    "secondary_translation": "nlt"
                },
                "date": {
                    "name": "Date Mode",
                    "description": "Biblical calendar events",
                    "background_index": 7,
                    "border_index": 5,
                    "font_name": "default",
                    "verse_font_size": 72,
                    "reference_font_size": 76,
                    "title_font_size": 44,
                    "display_scale": 1.0,
                    "parallel_mode": False,
                    "primary_translation": "kjv",
                    "secondary_translation": "esv"
                },
                "random": {
                    "name": "Random Mode",
                    "description": "Random Bible verses",
                    "background_index": 3,
                    "border_index": 2,
                    "font_name": "default",
                    "verse_font_size": 88,
                    "reference_font_size": 92,
                    "title_font_size": 52,
                    "display_scale": 1.0,
                    "parallel_mode": False,
                    "primary_translation": "nlt",
                    "secondary_translation": "msg"
                },
                "devotional": {
                    "name": "Devotional Mode",
                    "description": "Faith's Checkbook devotionals",
                    "background_index": 8,
                    "border_index": 8,
                    "font_name": "default",
                    "verse_font_size": 76,
                    "reference_font_size": 80,
                    "title_font_size": 46,
                    "display_scale": 1.0,
                    "parallel_mode": False,
                    "primary_translation": "kjv",
                    "secondary_translation": "nlt"
                },
                "weather": {
                    "name": "Weather Mode",
                    "description": "Forecast with Moon Phase",
                    "background_index": 4,
                    "border_index": 3,
                    "font_name": "default",
                    "verse_font_size": 32,
                    "reference_font_size": 28,
                    "title_font_size": 36,
                    "display_scale": 1.0,
                    "parallel_mode": False,
                    "primary_translation": "kjv",
                    "secondary_translation": "nlt"
                },
                "news": {
                    "name": "Israel News Mode",
                    "description": "Recent news from Israel",
                    "background_index": 6,
                    "border_index": 4,
                    "font_name": "default",
                    "verse_font_size": 32,
                    "reference_font_size": 28,
                    "title_font_size": 36,
                    "display_scale": 1.0,
                    "parallel_mode": False,
                    "primary_translation": "kjv",
                    "secondary_translation": "nlt"
                }
            }
        }
    
    def get_default_mode(self) -> str:
        """Get the default display mode for startup/restart."""
        return self.settings.get('default_mode', 'time')
    
    def set_default_mode(self, mode: str):
        """Set the default display mode for startup/restart."""
        if mode in self.get_available_modes():
            self.settings['default_mode'] = mode
            self._save_settings()
            self.logger.info(f"Default mode set to: {mode}")
        else:
            raise ValueError(f"Invalid mode: {mode}")
    
    def get_available_modes(self) -> list:
        """Get list of available display modes."""
        return list(self.settings.get('mode_settings', {}).keys())
    
    def get_mode_info(self, mode: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific mode."""
        return self.settings.get('mode_settings', {}).get(mode)
    
    def get_all_modes_info(self) -> Dict[str, Any]:
        """Get information about all modes."""
        modes_info = {}
        for mode in self.get_available_modes():
            mode_data = self.get_mode_info(mode)
            if mode_data:
                modes_info[mode] = {
                    'name': mode_data.get('name', mode.title()),
                    'description': mode_data.get('description', ''),
                    'is_default': mode == self.get_default_mode()
                }
        return modes_info
    
    def get_mode_settings(self, mode: str) -> Optional[Dict[str, Any]]:
        """Get all settings for a specific mode."""
        return self.settings.get('mode_settings', {}).get(mode)
    
    def update_mode_setting(self, mode: str, setting_key: str, value: Any):
        """Update a specific setting for a mode."""
        if mode not in self.get_available_modes():
            raise ValueError(f"Invalid mode: {mode}")
        
        if 'mode_settings' not in self.settings:
            self.settings['mode_settings'] = {}
        if mode not in self.settings['mode_settings']:
            self.settings['mode_settings'][mode] = {}
        
        self.settings['mode_settings'][mode][setting_key] = value
        self._save_settings()
        self.logger.info(f"Updated {mode} mode setting {setting_key} to {value}")
    
    def update_mode_settings(self, mode: str, settings_update: Dict[str, Any]):
        """Update multiple settings for a mode."""
        if mode not in self.get_available_modes():
            raise ValueError(f"Invalid mode: {mode}")
        
        if 'mode_settings' not in self.settings:
            self.settings['mode_settings'] = {}
        if mode not in self.settings['mode_settings']:
            self.settings['mode_settings'][mode] = {}
        
        self.settings['mode_settings'][mode].update(settings_update)
        self._save_settings()
        self.logger.info(f"Updated {mode} mode settings: {list(settings_update.keys())}")
    
    def reset_mode_to_defaults(self, mode: str):
        """Reset a mode to its default settings."""
        defaults = self._get_default_settings()
        if mode in defaults.get('mode_settings', {}):
            self.settings['mode_settings'][mode] = defaults['mode_settings'][mode].copy()
            self._save_settings()
            self.logger.info(f"Reset {mode} mode to defaults")
        else:
            raise ValueError(f"No default settings available for mode: {mode}")
    
    def apply_mode_settings_to_image_generator(self, image_generator, mode: str):
        """Apply mode-specific settings to the image generator."""
        mode_settings = self.get_mode_settings(mode)
        if not mode_settings:
            self.logger.warning(f"No settings found for mode: {mode}")
            return
        
        try:
            # Apply background/border settings
            if 'background_index' in mode_settings:
                image_generator.set_separate_background(mode_settings['background_index'])
            
            if 'border_index' in mode_settings:
                image_generator.set_separate_border(mode_settings['border_index'])
            
            # Apply font settings
            if 'font_name' in mode_settings:
                image_generator.set_font(mode_settings['font_name'])
            
            if 'verse_font_size' in mode_settings:
                image_generator.verse_size = mode_settings['verse_font_size']
            
            if 'reference_font_size' in mode_settings:
                image_generator.reference_size = mode_settings['reference_font_size']
            
            if 'title_font_size' in mode_settings:
                image_generator.title_size = mode_settings['title_font_size']
            
            # Apply display scale
            if 'display_scale' in mode_settings:
                image_generator.set_display_scale(mode_settings['display_scale'])
            
            self.logger.info(f"Applied {mode} mode settings to image generator")
            
        except Exception as e:
            self.logger.error(f"Error applying {mode} mode settings: {e}")
    
    def get_mode_setting(self, mode: str, setting_key: str, default=None):
        """Get a specific setting value for a mode."""
        mode_settings = self.get_mode_settings(mode)
        if mode_settings:
            return mode_settings.get(setting_key, default)
        return default