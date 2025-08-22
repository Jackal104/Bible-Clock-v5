"""
Weather Display Generator - Creates weather forecast displays for Bible Clock.
Generates 7-day weather forecasts for current location and Jerusalem with moon phases.
"""

import logging
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os
from weather_service import weather_service


class WeatherDisplayGenerator:
    """Generates weather display images for the Bible Clock."""
    
    def __init__(self, width: int = 800, height: int = 600):
        self.logger = logging.getLogger(__name__)
        self.width = width
        self.height = height
        
        # Colors (compatible with e-ink displays)
        self.colors = {
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'gray': (128, 128, 128),
            'light_gray': (192, 192, 192),
            'dark_gray': (64, 64, 64)
        }
        
        # Weather icon symbols (text-based for simplicity)
        self.weather_icons = {
            'clear': '☀',
            'partly_cloudy': '⛅',
            'cloudy': '☁',
            'overcast': '☁',
            'rain': '🌧',
            'drizzle': '🌦',
            'snow': '🌨',
            'thunderstorm': '⛈',
            'fog': '🌫',
            'unknown': '?'
        }
        
        # Moon phase symbols
        self.moon_phases = {
            'New Moon': '🌑',
            'Waxing Crescent': '🌒',
            'First Quarter': '🌓',
            'Waxing Gibbous': '🌔',
            'Full Moon': '🌕',
            'Waning Gibbous': '🌖',
            'Last Quarter': '🌗',
            'Waning Crescent': '🌘'
        }
        
        # Load fonts
        self._load_fonts()
    
    def _load_fonts(self):
        """Load fonts for the display."""
        try:
            # Try to load system fonts
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/System/Library/Fonts/Arial.ttf',
                '/Windows/Fonts/arial.ttf'
            ]
            
            font_path = None
            for path in font_paths:
                if os.path.exists(path):
                    font_path = path
                    break
            
            if font_path:
                self.fonts = {
                    'title': ImageFont.truetype(font_path, 36),
                    'header': ImageFont.truetype(font_path, 24),
                    'day': ImageFont.truetype(font_path, 18),
                    'temp': ImageFont.truetype(font_path, 16),
                    'small': ImageFont.truetype(font_path, 12),
                    'icon': ImageFont.truetype(font_path, 20)
                }
            else:
                # Fallback to default font
                self.fonts = {
                    'title': ImageFont.load_default(),
                    'header': ImageFont.load_default(),
                    'day': ImageFont.load_default(),
                    'temp': ImageFont.load_default(),
                    'small': ImageFont.load_default(),
                    'icon': ImageFont.load_default()
                }
            
            self.logger.info(f"Fonts loaded: {font_path or 'default'}")
            
        except Exception as e:
            self.logger.error(f"Failed to load fonts: {e}")
            # Use default fonts as fallback
            self.fonts = {
                'title': ImageFont.load_default(),
                'header': ImageFont.load_default(),
                'day': ImageFont.load_default(),
                'temp': ImageFont.load_default(),
                'small': ImageFont.load_default(),
                'icon': ImageFont.load_default()
            }
    
    def generate_weather_display(self) -> Optional[Image.Image]:
        """Generate the complete weather display image."""
        try:
            # Get weather data
            weather_data = weather_service.get_complete_weather_data()
            
            if not weather_data:
                return self._create_error_image("Failed to load weather data")
            
            # Create base image
            image = Image.new('RGB', (self.width, self.height), self.colors['white'])
            draw = ImageDraw.Draw(image)
            
            # Layout positions
            margin = 20
            y_pos = margin
            
            # Draw title
            title = "Weather Forecast"
            title_bbox = draw.textbbox((0, 0), title, font=self.fonts['title'])
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (self.width - title_width) // 2
            draw.text((title_x, y_pos), title, fill=self.colors['black'], font=self.fonts['title'])
            y_pos += 50
            
            # Draw current location weather
            current_location = weather_data.get('current_location')
            if current_location and current_location.get('weather'):
                y_pos = self._draw_location_weather(
                    draw, current_location, y_pos, "Current Location"
                )
            else:
                y_pos = self._draw_no_data_section(draw, y_pos, "Current Location: No data available")
            
            y_pos += 20
            
            # Draw second location weather
            second_location = weather_data.get('second_location')
            if second_location and second_location.get('weather'):
                location_name = second_location.get('location_info', {}).get('name', 'Second Location')
                y_pos = self._draw_location_weather(
                    draw, second_location, y_pos, location_name
                )
            else:
                y_pos = self._draw_no_data_section(draw, y_pos, "Second location: No data available")
            
            # Draw moon phases (if there's space)
            if y_pos < self.height - 80:
                self._draw_moon_phases(draw, weather_data.get('moon_phases'), y_pos)
            
            # Draw update timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            draw.text((10, self.height - 20), f"Updated: {timestamp}", 
                     fill=self.colors['gray'], font=self.fonts['small'])
            
            self.logger.info("Weather display generated successfully")
            return image
            
        except Exception as e:
            self.logger.error(f"Failed to generate weather display: {e}")
            return self._create_error_image(f"Error: {str(e)}")
    
    def _draw_location_weather(self, draw: ImageDraw.Draw, location_data: Dict, 
                              start_y: int, location_name: str) -> int:
        """Draw weather forecast for a specific location."""
        weather = location_data.get('weather', {})
        location_info = location_data.get('location_info', {})
        
        # Location header
        if location_info:
            location_text = f"{location_name}: {location_info.get('city', '')}, {location_info.get('country', '')}"
        else:
            location_text = location_name
        
        draw.text((20, start_y), location_text, fill=self.colors['black'], font=self.fonts['header'])
        y_pos = start_y + 30
        
        # Current weather
        current = weather.get('current', {})
        if current:
            temp = current.get('temperature', 0)
            temp_unit = current.get('temperature_unit', '°F')
            current_text = f"Now: {temp:.0f}{temp_unit} - {current.get('description', 'Unknown')}"
            draw.text((40, y_pos), current_text, fill=self.colors['dark_gray'], font=self.fonts['day'])
            y_pos += 25
        
        # 7-day forecast
        daily_forecast = weather.get('daily', [])
        if daily_forecast:
            # Draw forecast header
            draw.text((40, y_pos), "7-Day Forecast:", fill=self.colors['black'], font=self.fonts['day'])
            y_pos += 20
            
            # Calculate column widths
            day_width = 80
            col_width = (self.width - 100) // 7
            
            # Draw days in a grid
            for i, day in enumerate(daily_forecast[:7]):
                x_pos = 50 + (i * col_width)
                
                # Day name
                day_name = day.get('day_name', '')[:3]  # Abbreviate
                draw.text((x_pos, y_pos), day_name, fill=self.colors['black'], font=self.fonts['small'])
                
                # Weather icon (simple text representation)
                icon = self._get_weather_icon(day.get('weathercode', 0))
                draw.text((x_pos, y_pos + 15), icon, fill=self.colors['black'], font=self.fonts['icon'])
                
                # Temperatures
                temp_unit = day.get('temperature_unit', '°F')
                max_temp = f"{day.get('max_temp', 0):.0f}°"
                min_temp = f"{day.get('min_temp', 0):.0f}°"
                draw.text((x_pos, y_pos + 35), max_temp, fill=self.colors['black'], font=self.fonts['small'])
                draw.text((x_pos, y_pos + 50), min_temp, fill=self.colors['gray'], font=self.fonts['small'])
            
            y_pos += 70
        
        return y_pos
    
    def _draw_no_data_section(self, draw: ImageDraw.Draw, start_y: int, message: str) -> int:
        """Draw a no data available section."""
        draw.text((20, start_y), message, fill=self.colors['gray'], font=self.fonts['header'])
        return start_y + 40
    
    def _draw_moon_phases(self, draw: ImageDraw.Draw, moon_data: Optional[Dict], start_y: int):
        """Draw moon phase information."""
        if not moon_data:
            return
        
        # Moon phases header
        draw.text((20, start_y), "Moon Phases", fill=self.colors['black'], font=self.fonts['header'])
        y_pos = start_y + 25
        
        # Current illumination
        illumination = moon_data.get('current_illumination', 50)
        illum_text = f"Current illumination: {illumination}%"
        draw.text((40, y_pos), illum_text, fill=self.colors['dark_gray'], font=self.fonts['day'])
        y_pos += 20
        
        # Upcoming phases
        phases = moon_data.get('phases', [])
        if phases:
            for phase in phases[:3]:  # Show next 3 phases
                phase_name = phase.get('phase', '')
                phase_date = phase.get('date', '')
                phase_text = f"{phase_name}: {phase_date}"
                
                # Add moon icon if available
                moon_icon = self.moon_phases.get(phase_name, '🌙')
                full_text = f"{moon_icon} {phase_text}"
                
                draw.text((40, y_pos), full_text, fill=self.colors['dark_gray'], font=self.fonts['small'])
                y_pos += 15
    
    def _get_weather_icon(self, weather_code: int) -> str:
        """Get weather icon based on weather code."""
        if weather_code == 0:
            return self.weather_icons['clear']
        elif weather_code in [1, 2]:
            return self.weather_icons['partly_cloudy']
        elif weather_code == 3:
            return self.weather_icons['overcast']
        elif weather_code in [45, 48]:
            return self.weather_icons['fog']
        elif weather_code in [51, 53, 55]:
            return self.weather_icons['drizzle']
        elif weather_code in [61, 63, 65, 80, 81, 82]:
            return self.weather_icons['rain']
        elif weather_code in [71, 73, 75, 77, 85, 86]:
            return self.weather_icons['snow']
        elif weather_code in [95, 96, 99]:
            return self.weather_icons['thunderstorm']
        else:
            return self.weather_icons['unknown']
    
    def _create_error_image(self, error_message: str) -> Image.Image:
        """Create an error display image."""
        image = Image.new('RGB', (self.width, self.height), self.colors['white'])
        draw = ImageDraw.Draw(image)
        
        # Error title
        title = "Weather Display Error"
        title_bbox = draw.textbbox((0, 0), title, font=self.fonts['title'])
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (self.width - title_width) // 2
        draw.text((title_x, 100), title, fill=self.colors['black'], font=self.fonts['title'])
        
        # Error message
        draw.text((50, 200), error_message, fill=self.colors['gray'], font=self.fonts['header'])
        
        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        draw.text((10, self.height - 20), f"Error at: {timestamp}", 
                 fill=self.colors['gray'], font=self.fonts['small'])
        
        return image


# Global weather display generator instance
weather_display_generator = WeatherDisplayGenerator()