"""
Weather Settings Manager - Handles weather-specific configuration for Bible Clock.
Manages temperature units, locations, and weather display preferences.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional


class WeatherSettings:
    """Manages weather-specific settings."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.settings_file = Path('data/weather_settings.json')
        self.settings = self._load_settings()
        
    def _load_settings(self) -> Dict[str, Any]:
        """Load weather settings from file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                self.logger.info("Weather settings loaded")
                return settings
            except Exception as e:
                self.logger.error(f"Error loading weather settings: {e}")
        
        # Default settings if file doesn't exist or fails to load
        return self._get_default_settings()
    
    def _save_settings(self):
        """Save weather settings to file."""
        try:
            self.settings_file.parent.mkdir(exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            self.logger.info("Weather settings saved")
        except Exception as e:
            self.logger.error(f"Error saving weather settings: {e}")
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default weather settings."""
        return {
            "temperature_unit": "F",  # "F" for Fahrenheit, "C" for Celsius
            "auto_location": True,    # Use IP geolocation for current location
            "custom_location": {
                "enabled": False,
                "city": "",
                "country": "",
                "latitude": None,
                "longitude": None
            },
            "second_location": {
                "enabled": True,
                "name": "Jerusalem, Israel",
                "latitude": 31.7683,
                "longitude": 35.2137
            },
            "weather_refresh_minutes": 30,  # How often to refresh weather data
            "show_moon_phases": True,
            "show_wind_speed": True,
            "show_precipitation": True,
            "display_format": "detailed"  # "detailed" or "compact"
        }
    
    def get_setting(self, key: str, default=None):
        """Get a specific weather setting."""
        return self.settings.get(key, default)
    
    def update_setting(self, key: str, value: Any):
        """Update a specific weather setting."""
        self.settings[key] = value
        self._save_settings()
        self.logger.info(f"Weather setting updated: {key} = {value}")
    
    def update_settings(self, settings_update: Dict[str, Any]):
        """Update multiple weather settings."""
        self.settings.update(settings_update)
        self._save_settings()
        self.logger.info(f"Weather settings updated: {list(settings_update.keys())}")
    
    def get_temperature_unit(self) -> str:
        """Get the current temperature unit (F or C)."""
        return self.settings.get("temperature_unit", "F")
    
    def set_temperature_unit(self, unit: str):
        """Set the temperature unit."""
        if unit.upper() in ["F", "C", "FAHRENHEIT", "CELSIUS"]:
            unit_code = "F" if unit.upper() in ["F", "FAHRENHEIT"] else "C"
            self.update_setting("temperature_unit", unit_code)
        else:
            raise ValueError(f"Invalid temperature unit: {unit}. Use 'F' or 'C'")
    
    def get_custom_location(self) -> Optional[Dict[str, Any]]:
        """Get custom location settings if enabled."""
        custom = self.settings.get("custom_location", {})
        if custom.get("enabled", False):
            return custom
        return None
    
    def set_custom_location(self, city: str, country: str = "", latitude: float = None, longitude: float = None):
        """Set custom location settings."""
        self.update_setting("custom_location", {
            "enabled": True,
            "city": city,
            "country": country,
            "latitude": latitude,
            "longitude": longitude
        })
    
    def disable_custom_location(self):
        """Disable custom location and use auto-detection."""
        custom = self.settings.get("custom_location", {})
        custom["enabled"] = False
        self.update_setting("custom_location", custom)
        self.update_setting("auto_location", True)
    
    def get_second_location(self) -> Dict[str, Any]:
        """Get second location settings."""
        return self.settings.get("second_location", {
            "enabled": True,
            "name": "Jerusalem, Israel",
            "latitude": 31.7683,
            "longitude": 35.2137
        })
    
    def set_second_location(self, name: str, latitude: float, longitude: float):
        """Set second location settings."""
        self.update_setting("second_location", {
            "enabled": True,
            "name": name,
            "latitude": latitude,
            "longitude": longitude
        })
    
    def disable_second_location(self):
        """Disable second location display."""
        second = self.settings.get("second_location", {})
        second["enabled"] = False
        self.update_setting("second_location", second)
    
    def convert_temperature(self, temp_celsius: float) -> float:
        """Convert temperature from Celsius to the user's preferred unit."""
        if self.get_temperature_unit() == "F":
            return (temp_celsius * 9/5) + 32
        return temp_celsius
    
    def get_temperature_symbol(self) -> str:
        """Get the temperature symbol for display."""
        return "°F" if self.get_temperature_unit() == "F" else "°C"
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all weather settings."""
        return self.settings.copy()
    
    def reset_to_defaults(self):
        """Reset all weather settings to defaults."""
        self.settings = self._get_default_settings()
        self._save_settings()
        self.logger.info("Weather settings reset to defaults")


# Global weather settings instance
weather_settings = WeatherSettings()