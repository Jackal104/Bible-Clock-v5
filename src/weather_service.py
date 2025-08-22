"""
Weather Service - Handles weather data, location detection, and moon phases for Bible Clock.
Provides 7-day forecasts for current location and Jerusalem.
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json


class WeatherService:
    """Handles weather data retrieval and location detection."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Load weather settings
        try:
            from weather_settings import weather_settings
            self.weather_settings = weather_settings
        except Exception as e:
            self.logger.error(f"Failed to load weather settings: {e}")
            self.weather_settings = None
        
        # Jerusalem coordinates (for fixed location weather)
        self.jerusalem_coords = (31.7683, 35.2137)
        
        # Cache for location data
        self._location_cache = None
        self._location_cache_time = None
        self._weather_cache = {}
        
    def get_current_location(self) -> Optional[Dict]:
        """Get current location using custom settings or IP geolocation."""
        try:
            # Check if custom location is enabled
            if self.weather_settings:
                custom_location = self.weather_settings.get_custom_location()
                if custom_location and custom_location.get('enabled'):
                    location = {
                        'latitude': custom_location.get('latitude'),
                        'longitude': custom_location.get('longitude'),
                        'city': custom_location.get('city', 'Custom Location'),
                        'region': '',
                        'country': custom_location.get('country', ''),
                        'timezone': 'auto',
                        'is_custom': True
                    }
                    self.logger.info(f"Using custom location: {location['city']}, {location['country']}")
                    return location
            
            # Use cached location if less than 1 hour old
            if (self._location_cache and self._location_cache_time and 
                datetime.now() - self._location_cache_time < timedelta(hours=1)):
                return self._location_cache
            
            # IP-API.com - free, no API key required
            response = requests.get('http://ip-api.com/json/', timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'success':
                location = {
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon'),
                    'city': data.get('city'),
                    'region': data.get('regionName'),
                    'country': data.get('country'),
                    'timezone': data.get('timezone'),
                    'is_custom': False
                }
                
                # Cache the location
                self._location_cache = location
                self._location_cache_time = datetime.now()
                
                self.logger.info(f"Location detected: {location['city']}, {location['country']}")
                return location
            else:
                self.logger.error(f"Location API error: {data.get('message', 'Unknown error')}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get current location: {e}")
            return None
    
    def get_weather_forecast(self, latitude: float, longitude: float, location_name: str = "") -> Optional[Dict]:
        """Get 7-day weather forecast using Open-Meteo API."""
        try:
            cache_key = f"{latitude},{longitude}"
            
            # Use cached weather if less than 1 hour old (for hourly updates)
            if (cache_key in self._weather_cache and 
                datetime.now() - self._weather_cache[cache_key]['timestamp'] < timedelta(hours=1)):
                return self._weather_cache[cache_key]['data']
            
            # Open-Meteo API - free, no API key required
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': latitude,
                'longitude': longitude,
                'daily': 'temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum,windspeed_10m_max',
                'current_weather': 'true',
                'timezone': 'auto',
                'forecast_days': 7
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            # Process the weather data into a more usable format
            forecast = {
                'location': location_name,
                'latitude': latitude,
                'longitude': longitude,
                'current': self._parse_current_weather(data.get('current_weather', {})),
                'daily': self._parse_daily_forecast(data.get('daily', {})),
                'timezone': data.get('timezone', 'UTC')
            }
            
            # Cache the weather data
            self._weather_cache[cache_key] = {
                'data': forecast,
                'timestamp': datetime.now()
            }
            
            self.logger.info(f"Weather forecast retrieved for {location_name or 'location'}")
            return forecast
            
        except Exception as e:
            self.logger.error(f"Failed to get weather forecast for {location_name}: {e}")
            return None
    
    def _parse_current_weather(self, current_data: Dict) -> Dict:
        """Parse current weather data from Open-Meteo."""
        temp_celsius = current_data.get('temperature', 0)
        temp_display = self._convert_temperature(temp_celsius)
        temp_unit = self._get_temperature_symbol()
        
        return {
            'temperature': temp_display,
            'temperature_raw': temp_celsius,
            'temperature_unit': temp_unit,
            'windspeed': current_data.get('windspeed', 0),
            'weathercode': current_data.get('weathercode', 0),
            'time': current_data.get('time', ''),
            'description': self._get_weather_description(current_data.get('weathercode', 0))
        }
    
    def _parse_daily_forecast(self, daily_data: Dict) -> List[Dict]:
        """Parse daily forecast data from Open-Meteo."""
        if not daily_data:
            return []
        
        forecast_days = []
        dates = daily_data.get('time', [])
        max_temps = daily_data.get('temperature_2m_max', [])
        min_temps = daily_data.get('temperature_2m_min', [])
        weather_codes = daily_data.get('weathercode', [])
        precipitation = daily_data.get('precipitation_sum', [])
        wind_speeds = daily_data.get('windspeed_10m_max', [])
        
        for i in range(len(dates)):
            max_temp_c = max_temps[i] if i < len(max_temps) else 0
            min_temp_c = min_temps[i] if i < len(min_temps) else 0
            
            day = {
                'date': dates[i],
                'max_temp': self._convert_temperature(max_temp_c),
                'min_temp': self._convert_temperature(min_temp_c),
                'max_temp_raw': max_temp_c,
                'min_temp_raw': min_temp_c,
                'temperature_unit': self._get_temperature_symbol(),
                'weathercode': weather_codes[i] if i < len(weather_codes) else 0,
                'precipitation': precipitation[i] if i < len(precipitation) else 0,
                'wind_speed': wind_speeds[i] if i < len(wind_speeds) else 0,
                'description': self._get_weather_description(weather_codes[i] if i < len(weather_codes) else 0),
                'day_name': self._get_day_name(dates[i])
            }
            forecast_days.append(day)
        
        return forecast_days
    
    def _get_weather_description(self, weather_code: int) -> str:
        """Convert WMO weather code to description."""
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy", 
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snowfall",
            73: "Moderate snowfall",
            75: "Heavy snowfall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail"
        }
        return weather_codes.get(weather_code, "Unknown")
    
    def _get_day_name(self, date_str: str) -> str:
        """Get day name from date string."""
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%A')
        except:
            return "Unknown"
    
    def get_moon_phase_data(self, days: int = 7) -> Optional[Dict]:
        """Get moon phase data using built-in astronomical calculations."""
        try:
            today = datetime.now()
            
            # Calculate current moon illumination and phase
            current_illumination = self._calculate_moon_illumination()
            current_phase_name = self._get_moon_phase_name(current_illumination)
            
            # Calculate next major moon phases
            phases = []
            next_phases = self._calculate_next_moon_phases(today, days)
            
            for phase_data in next_phases:
                phases.append({
                    'date': phase_data['date'].strftime('%Y-%m-%d'),
                    'phase': phase_data['phase'],
                    'time': '12:00',  # Approximate time
                    'day_name': phase_data['date'].strftime('%A')
                })
            
            return {
                'phases': phases,
                'current_illumination': round(current_illumination, 1),
                'current_phase': current_phase_name,
                'updated': today.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate moon phase data: {e}")
            # Return fallback data so display shows something
            return {
                'phases': [{'date': today.strftime('%Y-%m-%d'), 'phase': 'Unknown', 'time': '12:00', 'day_name': today.strftime('%A')}],
                'current_illumination': 50.0,
                'current_phase': 'Half Moon',
                'updated': today.isoformat()
            }
    
    def _calculate_moon_illumination(self) -> float:
        """Calculate approximate moon illumination percentage."""
        try:
            # Simple calculation based on lunar cycle (29.5 days)
            # This is approximate - for precise calculations, we'd need astronomical libraries
            epoch = datetime(2000, 1, 6, 18, 14)  # New moon reference
            now = datetime.now()
            days_since_epoch = (now - epoch).total_seconds() / 86400
            lunar_cycle_position = (days_since_epoch % 29.53) / 29.53
            
            # Calculate illumination percentage
            if lunar_cycle_position <= 0.5:
                # Waxing (0 to 100%)
                illumination = lunar_cycle_position * 2 * 100
            else:
                # Waning (100% to 0)
                illumination = (1 - (lunar_cycle_position - 0.5) * 2) * 100
            
            return round(illumination, 1)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate moon illumination: {e}")
            return 50.0  # Default to 50%
    
    def _get_moon_phase_name(self, illumination: float) -> str:
        """Get moon phase name based on illumination percentage."""
        if illumination < 5:
            return "New Moon"
        elif illumination < 25:
            return "Waxing Crescent"
        elif illumination < 45:
            return "First Quarter"
        elif illumination < 55:
            return "Waxing Gibbous"
        elif illumination < 75:
            return "Full Moon"
        elif illumination < 95:
            return "Waning Gibbous"
        elif illumination < 100:
            return "Last Quarter"
        else:
            return "Waning Crescent"
    
    def _calculate_next_moon_phases(self, start_date: datetime, days: int) -> List[Dict]:
        """Calculate approximate dates of next major moon phases."""
        phases = []
        current_date = start_date
        
        # Major phases occur roughly every 7.4 days (29.5 day cycle / 4 phases)
        phase_names = ["New Moon", "First Quarter", "Full Moon", "Last Quarter"]
        
        # Find current phase position in cycle
        current_illumination = self._calculate_moon_illumination()
        
        # Estimate days to next phases (simplified calculation)
        lunar_cycle_day = (current_date - datetime(2000, 1, 6, 18, 14)).total_seconds() / 86400
        current_cycle_position = (lunar_cycle_day % 29.53) / 29.53 * 4  # 0-4 scale
        
        for i in range(4):  # Next 4 phases
            # Calculate days until next phase
            next_phase_position = (i + 1) % 4
            days_to_next = ((next_phase_position - current_cycle_position) % 4) * 7.4
            
            if days_to_next <= days:
                phase_date = current_date + timedelta(days=days_to_next)
                phases.append({
                    'date': phase_date,
                    'phase': phase_names[int(next_phase_position)]
                })
        
        return phases[:2]  # Return next 2 phases only
    
    def should_refresh_weather_data(self) -> bool:
        """Check if weather data should be refreshed (hourly check)."""
        try:
            # Check if any cached data is approaching expiration (within 5 minutes of 1 hour)
            now = datetime.now()
            for cache_data in self._weather_cache.values():
                time_diff = now - cache_data['timestamp']
                if time_diff >= timedelta(minutes=55):  # Refresh 5 minutes before expiration
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Error checking weather refresh status: {e}")
            return False
    
    def get_complete_weather_data(self, force_refresh: bool = False) -> Dict:
        """Get complete weather data for both current location and second location."""
        result = {
            'current_location': None,
            'second_location': None,
            'moon_phases': None,
            'updated': datetime.now().isoformat(),
            'temperature_unit': self._get_temperature_symbol()
        }
        
        try:
            # Clear cache if forced refresh
            if force_refresh:
                self._weather_cache.clear()
                self.logger.info("Weather cache cleared for forced refresh")
            
            # Get current location
            location = self.get_current_location()
            if location:
                current_weather = self.get_weather_forecast(
                    location['latitude'], 
                    location['longitude'],
                    f"{location['city']}, {location['country']}"
                )
                result['current_location'] = {
                    'location_info': location,
                    'weather': current_weather
                }
            
            # Get second location weather (default Jerusalem, but configurable)
            second_location = self._get_second_location()
            if second_location and second_location.get('enabled', True):
                second_weather = self.get_weather_forecast(
                    second_location['latitude'],
                    second_location['longitude'], 
                    second_location['name']
                )
                result['second_location'] = {
                    'location_info': second_location,
                    'weather': second_weather
                }
            
            # Get moon phase data
            result['moon_phases'] = self.get_moon_phase_data()
            
            self.logger.info("Complete weather data retrieved successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to get complete weather data: {e}")
        
        return result
    
    def _get_second_location(self) -> Dict:
        """Get second location settings."""
        if self.weather_settings:
            return self.weather_settings.get_second_location()
        else:
            # Fallback to Jerusalem
            return {
                "enabled": True,
                "name": "Jerusalem, Israel",
                "latitude": 31.7683,
                "longitude": 35.2137
            }
    
    def _convert_temperature(self, temp_celsius: float) -> float:
        """Convert temperature from Celsius to user's preferred unit."""
        if self.weather_settings:
            return self.weather_settings.convert_temperature(temp_celsius)
        else:
            # Default to Fahrenheit
            return (temp_celsius * 9/5) + 32
    
    def _get_temperature_symbol(self) -> str:
        """Get temperature symbol for display."""
        if self.weather_settings:
            return self.weather_settings.get_temperature_symbol()
        else:
            # Default to Fahrenheit
            return "°F"


# Global weather service instance
weather_service = WeatherService()