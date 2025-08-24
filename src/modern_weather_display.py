"""
Modern Weather Display Generator - Creates beautiful card-based weather displays.
Features modern typography, visual hierarchy, and e-ink optimized design.
"""

import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os
import math
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for older Python versions
    ZoneInfo = None
from weather_service import weather_service


class ModernWeatherDisplay:
    """Generates modern, card-based weather displays optimized for e-ink."""
    
    def __init__(self, width: int = 800, height: int = 600):
        self.logger = logging.getLogger(__name__)
        self.width = width
        self.height = height
        
        # Responsive design breakpoints
        self.is_large_display = width >= 1400  # Large e-ink displays
        self.is_medium_display = 800 <= width < 1400  # Medium displays
        self.is_small_display = width < 800  # Small displays
        
        # Scale factors for responsive design
        self.scale_factor = self._calculate_scale_factor()
        
        # Modern grayscale palette optimized for e-ink
        self.colors = {
            'black': 0,           # Pure black for headers
            'dark': 32,           # Dark gray for primary text
            'medium': 64,         # Medium gray for secondary text
            'light': 128,         # Light gray for subtle elements
            'lighter': 192,       # Very light gray for backgrounds
            'white': 255          # Pure white for backgrounds
        }
        
        # Card design constants (scaled) - Further increased for better visibility and spacing
        self.card_radius = int(24 * self.scale_factor)      # Increased from 20
        self.card_shadow = int(8 * self.scale_factor)       # Increased from 6
        self.card_padding = int(40 * self.scale_factor)     # Increased from 32
        self.card_margin = int(32 * self.scale_factor)      # Increased from 24
        
        # Typography hierarchy - DOUBLED fonts for maximum readability
        if self.width >= 1800:  # Very large displays - make fonts GIGANTIC
            base_font_sizes = {
                'hero': 480,          # GIGANTIC temperature display - DOUBLED from 240
                'h1': 280,            # Huge headers - DOUBLED from 140
                'h2': 200,            # Large section headers - DOUBLED from 100
                'h3': 160,            # Big location names - DOUBLED from 80
                'body': 120,          # Large weather description - DOUBLED from 60
                'caption': 100,       # Big details - DOUBLED from 50
                'micro': 80           # Medium text - DOUBLED from 40
            }
        else:  # Medium and smaller displays
            base_font_sizes = {
                'hero': 90,           # Large temperature display
                'h1': 60,             # Main headers
                'h2': 45,             # Section headers
                'h3': 35,             # Card titles
                'body': 28,           # Regular text
                'caption': 22,        # Small text
                'micro': 18           # Tiny labels
            }
        
        # Scale font sizes based on display size
        self.font_sizes = {
            name: int(size * self.scale_factor) 
            for name, size in base_font_sizes.items()
        }
        
        # Load modern fonts
        self._load_fonts()
        
        # Weather icon mappings - Using simple text symbols for better e-ink readability
        self.weather_icons = {
            'clear': 'SUN',
            'partly_cloudy': 'P.CLY',
            'cloudy': 'CLDY',
            'overcast': 'OVRC',
            'rain': 'RAIN',
            'drizzle': 'DRZL',
            'heavy_rain': 'H.RN',
            'snow': 'SNOW',
            'thunderstorm': 'STRM',
            'fog': 'FOG',
            'unknown': '---'
        }
        
        # Moon phase icons
        self.moon_icons = {
            'New Moon': '🌑',
            'Waxing Crescent': '🌒',
            'First Quarter': '🌓',
            'Waxing Gibbous': '🌔',
            'Full Moon': '🌕',
            'Waning Gibbous': '🌖',
            'Last Quarter': '🌗',
            'Waning Crescent': '🌘'
        }
    
    def _calculate_scale_factor(self) -> float:
        """Calculate scale factor based on display size - Fixed for 1872x1404."""
        if self.width >= 1800:  # Very large displays like 1872x1404
            return 1.0  # Don't scale up - use base sizes
        elif self.is_large_display:
            return 1.2  # Moderate scale up for large displays
        elif self.is_small_display:
            return 0.8  # Scale down for small displays
        else:
            return 1.0  # Default scale for medium displays
        
    def _load_fonts(self):
        """Load modern fonts optimized for e-ink displays."""
        try:
            # Priority order for font loading
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                '/System/Library/Fonts/Arial.ttf',
                '/Windows/Fonts/arial.ttf'
            ]
            
            base_font_path = None
            for path in font_paths:
                if os.path.exists(path):
                    base_font_path = path
                    break
            
            if base_font_path:
                self.fonts = {}
                for name, size in self.font_sizes.items():
                    try:
                        self.fonts[name] = ImageFont.truetype(base_font_path, size)
                    except Exception:
                        self.fonts[name] = ImageFont.load_default()
                
                self.logger.info(f"Modern fonts loaded: {base_font_path}")
            else:
                # Fallback to default fonts
                self.fonts = {name: ImageFont.load_default() for name in self.font_sizes.keys()}
                self.logger.warning("Using default fonts - text may not render optimally")
                
        except Exception as e:
            self.logger.error(f"Font loading error: {e}")
            self.fonts = {name: ImageFont.load_default() for name in self.font_sizes.keys()}
    
    def generate_modern_weather_display(self) -> Optional[Image.Image]:
        """Generate a modern, card-based weather display."""
        try:
            # Get weather data
            weather_data = weather_service.get_complete_weather_data()
            
            if not weather_data:
                return self._create_error_card("Weather data unavailable")
            
            # Create base image with soft gradient background
            image = self._create_background()
            draw = ImageDraw.Draw(image)
            
            # Layout calculation
            y_offset = 20
            
            # Title header
            y_offset = self._draw_title_header(draw, y_offset)
            
            # Side-by-side detailed weather layout (like XDA example)
            margin = 40
            center_line = self.width // 2
            column_width = center_line - (margin * 2)
            
            # Left side: Current location with full details
            left_x = margin
            self._draw_detailed_weather_location(
                draw, weather_data.get('current_location'), 
                weather_data.get('moon_phases'),
                left_x, y_offset, column_width, "CURRENT"
            )
            
            # Right side: Second location with full details
            right_x = center_line + margin
            self._draw_detailed_weather_location(
                draw, weather_data.get('second_location'),
                weather_data.get('moon_phases'),
                right_x, y_offset, column_width, "SECOND"
            )
            
            # Center divider line
            line_x = center_line
            draw.line([(line_x, y_offset), (line_x, self.height - 50)], 
                     fill=self.colors['lighter'], width=2)
            
            # Footer with update time
            self._draw_footer(draw, weather_data.get('updated'))
            
            self.logger.info("Modern weather display generated successfully")
            return image
            
        except Exception as e:
            self.logger.error(f"Failed to generate modern weather display: {e}")
            return self._create_error_card(f"Display Error: {str(e)}")
    
    def _create_background(self) -> Image.Image:
        """Create a modern gradient background optimized for e-ink."""
        image = Image.new('L', (self.width, self.height), self.colors['white'])
        
        # Subtle gradient overlay for depth
        draw = ImageDraw.Draw(image)
        
        # Very subtle vertical gradient
        for y in range(self.height):
            gradient_factor = y / self.height
            color_value = int(self.colors['white'] - (gradient_factor * 8))
            draw.line([(0, y), (self.width, y)], fill=color_value)
        
        return image
    
    def _draw_title_header(self, draw: ImageDraw.Draw, y_offset: int) -> int:
        """Draw the main title header."""
        title = "Weather Forecast"
        
        # Get text dimensions
        title_bbox = draw.textbbox((0, 0), title, font=self.fonts['h1'])
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        
        # Center title
        title_x = (self.width - title_width) // 2
        
        # Draw title with subtle shadow effect
        draw.text((title_x + 1, y_offset + 1), title, 
                 fill=self.colors['light'], font=self.fonts['h1'])
        draw.text((title_x, y_offset), title, 
                 fill=self.colors['black'], font=self.fonts['h1'])
        
        # Subtle underline
        line_y = y_offset + title_height + 6
        line_margin = 40
        draw.line([(line_margin, line_y), (self.width - line_margin, line_y)], 
                 fill=self.colors['lighter'], width=1)
        
        return y_offset + title_height + 20
    
    def _draw_current_location_card(self, draw: ImageDraw.Draw, location_data: Optional[Dict],
                                   x: int, y: int, width: int) -> int:
        """Draw current location weather card."""
        if not location_data or not location_data.get('weather'):
            return self._draw_no_data_card(draw, "Current Location", 
                                         "Location data unavailable", x, y, width)
        
        location_info = location_data.get('location_info', {})
        weather = location_data.get('weather', {})
        current = weather.get('current', {})
        
        # Card header
        city = location_info.get('city', 'Unknown')
        country = location_info.get('country', '')
        location_title = f"{city}"
        if country:
            location_title += f", {country}"
        
        card_y = y
        
        # Draw card background
        card_height = 140
        self._draw_card_background(draw, x, card_y, width, card_height)
        
        # Card content
        content_x = x + self.card_padding
        content_y = card_y + self.card_padding
        content_width = width - (2 * self.card_padding)
        
        # Location title
        draw.text((content_x, content_y), location_title, 
                 fill=self.colors['black'], font=self.fonts['h3'])
        content_y += 22
        
        # Current temperature (hero display)
        temp = current.get('temperature', 0)
        temp_unit = current.get('temperature_unit', '°F')
        temp_text = f"{temp:.0f}{temp_unit}"
        
        # Large temperature display
        temp_bbox = draw.textbbox((0, 0), temp_text, font=self.fonts['hero'])
        temp_width = temp_bbox[2] - temp_bbox[0]
        temp_x = content_x + (content_width - temp_width) // 2
        
        draw.text((temp_x, content_y), temp_text, 
                 fill=self.colors['black'], font=self.fonts['hero'])
        
        # Better spacing for description - more space for large displays
        desc_y = content_y + (70 if self.width >= 1800 else 52)
        
        # Weather description
        description = current.get('description', 'Unknown')
        weather_icon = self._get_weather_icon_for_code(current.get('weathercode', 0))
        desc_text = f"{weather_icon} {description}"
        
        desc_bbox = draw.textbbox((0, 0), desc_text, font=self.fonts['body'])
        desc_width = desc_bbox[2] - desc_bbox[0]
        desc_x = content_x + (content_width - desc_width) // 2
        
        draw.text((desc_x, desc_y), desc_text, 
                 fill=self.colors['medium'], font=self.fonts['body'])
        
        return card_y + card_height + self.card_margin
    
    def _draw_second_location_card(self, draw: ImageDraw.Draw, location_data: Optional[Dict],
                                  x: int, y: int, width: int) -> int:
        """Draw second location weather card."""
        if not location_data or not location_data.get('weather'):
            return self._draw_no_data_card(draw, "Second Location", 
                                         "No second location configured", x, y, width)
        
        location_info = location_data.get('location_info', {})
        weather = location_data.get('weather', {})
        current = weather.get('current', {})
        
        # Card header
        location_name = location_info.get('name', 'Second Location')
        
        card_y = y
        
        # Draw card background
        card_height = 140
        self._draw_card_background(draw, x, card_y, width, card_height)
        
        # Card content
        content_x = x + self.card_padding
        content_y = card_y + self.card_padding
        content_width = width - (2 * self.card_padding)
        
        # Location title
        draw.text((content_x, content_y), location_name, 
                 fill=self.colors['black'], font=self.fonts['h3'])
        content_y += 22
        
        # Current temperature (hero display)
        temp = current.get('temperature', 0)
        temp_unit = current.get('temperature_unit', '°F')
        temp_text = f"{temp:.0f}{temp_unit}"
        
        # Large temperature display
        temp_bbox = draw.textbbox((0, 0), temp_text, font=self.fonts['hero'])
        temp_width = temp_bbox[2] - temp_bbox[0]
        temp_x = content_x + (content_width - temp_width) // 2
        
        draw.text((temp_x, content_y), temp_text, 
                 fill=self.colors['black'], font=self.fonts['hero'])
        
        # Better spacing for description - more space for large displays
        desc_y = content_y + (70 if self.width >= 1800 else 52)
        
        # Weather description
        description = current.get('description', 'Unknown')
        weather_icon = self._get_weather_icon_for_code(current.get('weathercode', 0))
        desc_text = f"{weather_icon} {description}"
        
        desc_bbox = draw.textbbox((0, 0), desc_text, font=self.fonts['body'])
        desc_width = desc_bbox[2] - desc_bbox[0]
        desc_x = content_x + (content_width - desc_width) // 2
        
        draw.text((desc_x, desc_y), desc_text, 
                 fill=self.colors['medium'], font=self.fonts['body'])
        
        return card_y + card_height + self.card_margin
    
    def _draw_forecast_cards(self, draw: ImageDraw.Draw, weather_data: Dict,
                           x: int, y: int, width: int) -> int:
        """Draw 7-day forecast as horizontal cards."""
        # Use current location forecast, fallback to second location
        daily_forecast = None
        temp_unit = weather_data.get('temperature_unit', '°F')
        
        current_location = weather_data.get('current_location')
        if current_location and current_location.get('weather'):
            daily_forecast = current_location['weather'].get('daily', [])
        
        if not daily_forecast:
            second_location = weather_data.get('second_location')
            if second_location and second_location.get('weather'):
                daily_forecast = second_location['weather'].get('daily', [])
        
        if not daily_forecast:
            return self._draw_no_data_card(draw, "7-Day Forecast", 
                                         "Forecast data unavailable", x, y, width)
        
        # Section header
        draw.text((x, y), "7-Day Forecast", fill=self.colors['black'], font=self.fonts['h2'])
        card_y = y + 30
        
        # Calculate card dimensions - Properly spaced for display size
        cards_per_row = 7
        if self.width >= 1800:  # Large displays need much more spacing
            card_margin = 20
            card_width = max(200, (width - ((cards_per_row + 1) * card_margin)) // cards_per_row)
            card_height = 120  # Taller for large displays
        else:
            card_margin = 8
            card_width = max(80, (width - (cards_per_row * card_margin)) // cards_per_row)
            card_height = 80
        
        # Draw forecast cards with proper spacing
        for i, day in enumerate(daily_forecast[:7]):
            if self.width >= 1800:
                card_x = x + card_margin + (i * (card_width + card_margin))
            else:
                card_x = x + (i * (card_width + card_margin))
            
            # Draw card background
            self._draw_card_background(draw, card_x, card_y, card_width, card_height, mini=True)
            
            # Card content with minimal padding
            content_x = card_x + 4
            content_y = card_y + 4
            content_width = card_width - 8
            
            # Day name
            day_name = day.get('day_name', '')[:3]
            day_bbox = draw.textbbox((0, 0), day_name, font=self.fonts['caption'])
            day_width = day_bbox[2] - day_bbox[0]
            day_x = content_x + (content_width - day_width) // 2
            
            draw.text((day_x, content_y), day_name, 
                     fill=self.colors['dark'], font=self.fonts['caption'])
            content_y += 14
            
            # Weather icon
            weather_icon = self._get_weather_icon_for_code(day.get('weathercode', 0))
            icon_bbox = draw.textbbox((0, 0), weather_icon, font=self.fonts['micro'])
            icon_width = icon_bbox[2] - icon_bbox[0]
            icon_x = content_x + (content_width - icon_width) // 2
            
            draw.text((icon_x, content_y), weather_icon, 
                     fill=self.colors['dark'], font=self.fonts['micro'])
            content_y += 12
            
            # Temperatures combined on one line
            max_temp = f"{day.get('max_temp', 0):.0f}°"
            min_temp = f"{day.get('min_temp', 0):.0f}°"
            temp_text = f"{max_temp}/{min_temp}"
            
            temp_bbox = draw.textbbox((0, 0), temp_text, font=self.fonts['micro'])
            temp_width = temp_bbox[2] - temp_bbox[0]
            temp_x = content_x + (content_width - temp_width) // 2
            
            draw.text((temp_x, content_y), temp_text, 
                     fill=self.colors['black'], font=self.fonts['micro'])
        
        return card_y + card_height + self.card_margin
    
    def _draw_moon_phase_card(self, draw: ImageDraw.Draw, moon_data: Optional[Dict],
                            x: int, y: int, width: int) -> int:
        """Draw moon phase information card."""
        if not moon_data:
            return y
        
        # Section header
        draw.text((x, y), "Moon Phases", fill=self.colors['black'], font=self.fonts['h2'])
        card_y = y + 30
        
        card_height = 60
        self._draw_card_background(draw, x, card_y, width, card_height)
        
        # Card content
        content_x = x + self.card_padding
        content_y = card_y + self.card_padding
        
        # Current illumination
        illumination = moon_data.get('current_illumination', 50)
        illum_text = f"🌙 Current illumination: {illumination}%"
        draw.text((content_x, content_y), illum_text, 
                 fill=self.colors['dark'], font=self.fonts['body'])
        content_y += 18
        
        # Next phases
        phases = moon_data.get('phases', [])
        if phases:
            next_phase = phases[0]
            phase_text = f"Next: {next_phase.get('phase', '')} on {next_phase.get('date', '')}"
            draw.text((content_x, content_y), phase_text, 
                     fill=self.colors['medium'], font=self.fonts['caption'])
        
        return card_y + card_height + self.card_margin
    
    def _draw_card_background(self, draw: ImageDraw.Draw, x: int, y: int, 
                            width: int, height: int, mini: bool = False):
        """Draw a modern card background with subtle shadow."""
        # Shadow effect (offset by 2 pixels)
        if not mini:
            shadow_offset = 2
            draw.rounded_rectangle(
                [x + shadow_offset, y + shadow_offset, x + width + shadow_offset, y + height + shadow_offset],
                radius=self.card_radius,
                fill=self.colors['light']
            )
        
        # Main card background
        draw.rounded_rectangle(
            [x, y, x + width, y + height],
            radius=self.card_radius if not mini else 6,
            fill=self.colors['white'],
            outline=self.colors['lighter'],
            width=1
        )
    
    def _draw_no_data_card(self, draw: ImageDraw.Draw, title: str, message: str,
                          x: int, y: int, width: int) -> int:
        """Draw a card indicating no data available."""
        card_height = 80
        self._draw_card_background(draw, x, y, width, card_height)
        
        content_x = x + self.card_padding
        content_y = y + self.card_padding
        
        # Title
        draw.text((content_x, content_y), title, 
                 fill=self.colors['black'], font=self.fonts['h3'])
        content_y += 22
        
        # Message
        draw.text((content_x, content_y), message, 
                 fill=self.colors['medium'], font=self.fonts['body'])
        
        return y + card_height + self.card_margin
    
    def _draw_footer(self, draw: ImageDraw.Draw, updated_time: Optional[str]):
        """Draw footer with update timestamp."""
        if updated_time:
            try:
                dt = datetime.fromisoformat(updated_time.replace('Z', '+00:00'))
                footer_text = f"Updated: {dt.strftime('%I:%M %p')}"
            except:
                footer_text = "Updated: Recently"
        else:
            footer_text = "Updated: Unknown"
        
        # Right-align footer text
        footer_bbox = draw.textbbox((0, 0), footer_text, font=self.fonts['micro'])
        footer_width = footer_bbox[2] - footer_bbox[0]
        footer_x = self.width - footer_width - 10
        footer_y = self.height - 15
        
        draw.text((footer_x, footer_y), footer_text, 
                 fill=self.colors['light'], font=self.fonts['micro'])
    
    def _get_weather_icon_for_code(self, weather_code: int) -> str:
        """Get weather icon for weather code."""
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
        elif weather_code in [61, 63, 65]:
            return self.weather_icons['rain']
        elif weather_code in [80, 81, 82]:
            return self.weather_icons['heavy_rain']
        elif weather_code in [71, 73, 75, 77, 85, 86]:
            return self.weather_icons['snow']
        elif weather_code in [95, 96, 99]:
            return self.weather_icons['thunderstorm']
        else:
            return self.weather_icons['unknown']
    
    def _get_weather_emoji(self, weather_code: int) -> str:
        """Get weather emoji for weather code."""
        if weather_code == 0:
            return "☀️"  # Clear sky
        elif weather_code in [1, 2]:
            return "⛅"  # Partly cloudy
        elif weather_code == 3:
            return "☁️"  # Overcast
        elif weather_code in [45, 48]:
            return "🌫️"  # Fog
        elif weather_code in [51, 53, 55]:
            return "🌦️"  # Drizzle
        elif weather_code in [61, 63, 65]:
            return "🌧️"  # Rain
        elif weather_code in [80, 81, 82]:
            return "🌧️"  # Heavy rain
        elif weather_code in [71, 73, 75, 77, 85, 86]:
            return "❄️"  # Snow
        elif weather_code in [95, 96, 99]:
            return "⛈️"  # Thunderstorm
        else:
            return "🌤️"  # Unknown/default
    
    def _get_moon_emoji(self, phase_name: str) -> str:
        """Get appropriate moon emoji for phase name."""
        phase_lower = phase_name.lower()
        if 'new' in phase_lower:
            return "🌑"  # New Moon
        elif 'waxing crescent' in phase_lower:
            return "🌒"  # Waxing Crescent
        elif 'first quarter' in phase_lower:
            return "🌓"  # First Quarter
        elif 'waxing gibbous' in phase_lower:
            return "🌔"  # Waxing Gibbous
        elif 'full' in phase_lower:
            return "🌕"  # Full Moon
        elif 'waning gibbous' in phase_lower:
            return "🌖"  # Waning Gibbous
        elif 'last quarter' in phase_lower or 'third quarter' in phase_lower:
            return "🌗"  # Last Quarter
        elif 'waning crescent' in phase_lower:
            return "🌘"  # Waning Crescent
        else:
            return "🌙"  # Default moon
    
    def _create_error_card(self, error_message: str) -> Image.Image:
        """Create an error display."""
        image = self._create_background()
        draw = ImageDraw.Draw(image)
        
        # Center error message
        error_y = self.height // 2 - 40
        
        # Error card
        card_width = 400
        card_height = 80
        card_x = (self.width - card_width) // 2
        
        self._draw_card_background(draw, card_x, error_y, card_width, card_height)
        
        # Error content
        content_x = card_x + self.card_padding
        content_y = error_y + self.card_padding
        
        draw.text((content_x, content_y), "Weather Display Error", 
                 fill=self.colors['black'], font=self.fonts['h3'])
        content_y += 22
        
        draw.text((content_x, content_y), error_message, 
                 fill=self.colors['medium'], font=self.fonts['body'])
        
        return image
    
    def _draw_simple_current_weather(self, draw: ImageDraw.Draw, location_data: Optional[Dict],
                                    x: int, y: int, width: int) -> int:
        """Draw simple, large current weather display."""
        if not location_data or not location_data.get('weather'):
            draw.text((x, y), "Weather unavailable", 
                     fill=self.colors['medium'], font=self.fonts['h2'])
            return y + 100
        
        location_info = location_data.get('location_info', {})
        weather = location_data.get('weather', {})
        current = weather.get('current', {})
        
        # Location name (large)
        city = location_info.get('city', 'Unknown')
        country = location_info.get('country', '')
        location_text = f"{city}"
        if country:
            location_text += f", {country}"
        
        draw.text((x, y), location_text, 
                 fill=self.colors['black'], font=self.fonts['h2'])
        y += 100
        
        # Temperature (massive)
        temp = current.get('temperature', 0)
        temp_unit = current.get('temperature_unit', '°F')
        temp_text = f"{temp:.0f}{temp_unit}"
        
        draw.text((x, y), temp_text, 
                 fill=self.colors['black'], font=self.fonts['hero'])
        y += 200
        
        # Weather description (large)
        description = current.get('description', 'Unknown')
        weather_icon = self._get_weather_icon_for_code(current.get('weathercode', 0))
        desc_text = f"{weather_icon} - {description}"
        
        draw.text((x, y), desc_text, 
                 fill=self.colors['medium'], font=self.fonts['body'])
        
        return y + 80
    
    def _draw_simple_second_weather(self, draw: ImageDraw.Draw, location_data: Optional[Dict],
                                   x: int, y: int, width: int) -> int:
        """Draw simple, large second location weather."""
        if not location_data or not location_data.get('weather'):
            return y
        
        location_info = location_data.get('location_info', {})
        weather = location_data.get('weather', {})
        current = weather.get('current', {})
        
        # Location name
        location_name = location_info.get('name', 'Second Location')
        draw.text((x, y), location_name, 
                 fill=self.colors['black'], font=self.fonts['h2'])
        y += 100
        
        # Temperature (massive)
        temp = current.get('temperature', 0)
        temp_unit = current.get('temperature_unit', '°F')
        temp_text = f"{temp:.0f}{temp_unit}"
        
        draw.text((x, y), temp_text, 
                 fill=self.colors['black'], font=self.fonts['hero'])
        y += 200
        
        # Weather description
        description = current.get('description', 'Unknown')
        weather_icon = self._get_weather_icon_for_code(current.get('weathercode', 0))
        desc_text = f"{weather_icon} - {description}"
        
        draw.text((x, y), desc_text, 
                 fill=self.colors['medium'], font=self.fonts['body'])
        
        return y + 80
    
    def _draw_split_location_with_moon(self, draw: ImageDraw.Draw, location_data: Optional[Dict],
                                     moon_data: Optional[Dict], x: int, y: int, width: int, side: str) -> int:
        """Draw weather and moon information for split-screen layout."""
        current_y = y
        
        # Weather section
        current_y = self._draw_split_weather_section(draw, location_data, x, current_y, width, side)
        
        # Add some space before moon info
        current_y += 60
        
        # Moon section for this location
        current_y = self._draw_split_moon_section(draw, moon_data, x, current_y, width, side)
        
        return current_y
    
    def _draw_split_weather_section(self, draw: ImageDraw.Draw, location_data: Optional[Dict],
                                    x: int, y: int, width: int, side: str) -> int:
        """Draw weather for split-screen layout."""
        if not location_data or not location_data.get('weather'):
            draw.text((x, y + 100), "Weather unavailable", 
                     fill=self.colors['medium'], font=self.fonts['h2'])
            return y + 200
        
        location_info = location_data.get('location_info', {})
        weather = location_data.get('weather', {})
        current = weather.get('current', {})
        
        # Location name (large, centered in column)
        if side == "LEFT":
            city = location_info.get('city', 'Unknown')
            country = location_info.get('country', '')
            location_text = f"{city}"
            if country:
                location_text += f", {country}"
        else:
            location_text = location_info.get('name', 'Jerusalem, Israel')
        
        # Center the location name in its column
        location_bbox = draw.textbbox((0, 0), location_text, font=self.fonts['h2'])
        location_width = location_bbox[2] - location_bbox[0]
        location_x = x + (width - location_width) // 2
        
        draw.text((location_x, y), location_text, 
                 fill=self.colors['black'], font=self.fonts['h2'])
        y += 250  # DOUBLED spacing for gigantic fonts
        
        # Temperature (massive, centered)
        temp = current.get('temperature', 0)
        temp_unit = current.get('temperature_unit', '°F')
        temp_text = f"{temp:.0f}{temp_unit}"
        
        temp_bbox = draw.textbbox((0, 0), temp_text, font=self.fonts['hero'])
        temp_width = temp_bbox[2] - temp_bbox[0]
        temp_x = x + (width - temp_width) // 2
        
        draw.text((temp_x, y), temp_text, 
                 fill=self.colors['black'], font=self.fonts['hero'])
        y += 520  # DOUBLED spacing for gigantic temperature font
        
        # Weather description (centered)
        description = current.get('description', 'Unknown')
        weather_icon = self._get_weather_icon_for_code(current.get('weathercode', 0))
        desc_text = f"{weather_icon} - {description}"
        
        desc_bbox = draw.textbbox((0, 0), desc_text, font=self.fonts['body'])
        desc_width = desc_bbox[2] - desc_bbox[0]
        desc_x = x + (width - desc_width) // 2
        
        draw.text((desc_x, y), desc_text, 
                 fill=self.colors['medium'], font=self.fonts['body'])
        y += 140
        
        # Add fun temperature-based ASCII art
        temp_art = self._get_temperature_art(temp)
        if temp_art:
            art_lines = temp_art.split('\n')
            for line in art_lines:
                if line.strip():  # Skip empty lines
                    line_bbox = draw.textbbox((0, 0), line, font=self.fonts['micro'])
                    line_width = line_bbox[2] - line_bbox[0]
                    line_x = x + (width - line_width) // 2
                    
                    draw.text((line_x, y), line, 
                             fill=self.colors['medium'], font=self.fonts['micro'])
                    y += 50  # Spacing between art lines
        
        return y + 40
    
    def _draw_split_moon_section(self, draw: ImageDraw.Draw, moon_data: Optional[Dict],
                                x: int, y: int, width: int, side: str) -> int:
        """Draw moon phase information for each location side."""
        # Moon header (centered)
        moon_title = "Moon Phase"
        title_bbox = draw.textbbox((0, 0), moon_title, font=self.fonts['h3'])
        title_width = title_bbox[2] - title_bbox[0]
        title_x = x + (width - title_width) // 2
        
        draw.text((title_x, y), moon_title, 
                 fill=self.colors['black'], font=self.fonts['h3'])
        y += 100
        
        if not moon_data:
            # Show message when no moon data available
            no_data_text = "Data unavailable"
            no_data_bbox = draw.textbbox((0, 0), no_data_text, font=self.fonts['caption'])
            no_data_width = no_data_bbox[2] - no_data_bbox[0]
            no_data_x = x + (width - no_data_width) // 2
            
            draw.text((no_data_x, y), no_data_text, 
                     fill=self.colors['medium'], font=self.fonts['caption'])
            return y + 80
        
        # Current illumination (large, centered)
        illumination = moon_data.get('current_illumination', 50)
        illum_text = f"{illumination}% Illuminated"
        illum_bbox = draw.textbbox((0, 0), illum_text, font=self.fonts['caption'])
        illum_width = illum_bbox[2] - illum_bbox[0]
        illum_x = x + (width - illum_width) // 2
        
        draw.text((illum_x, y), illum_text, 
                 fill=self.colors['dark'], font=self.fonts['caption'])
        y += 80
        
        # Next phase (if available, centered)
        phases = moon_data.get('phases', [])
        if phases:
            next_phase = phases[0]
            phase_name = next_phase.get('phase', '')
            phase_date = next_phase.get('date', '')
            if phase_name and phase_date:
                phase_text = f"Next: {phase_name}"
                phase_bbox = draw.textbbox((0, 0), phase_text, font=self.fonts['micro'])
                phase_width = phase_bbox[2] - phase_bbox[0]
                phase_x = x + (width - phase_width) // 2
                
                draw.text((phase_x, y), phase_text, 
                         fill=self.colors['medium'], font=self.fonts['micro'])
                y += 60
                
                # Date on separate line
                date_bbox = draw.textbbox((0, 0), phase_date, font=self.fonts['micro'])
                date_width = date_bbox[2] - date_bbox[0]
                date_x = x + (width - date_width) // 2
                
                draw.text((date_x, y), phase_date, 
                         fill=self.colors['medium'], font=self.fonts['micro'])
        
        return y + 60
    
    def _draw_bottom_moon_info(self, draw: ImageDraw.Draw, moon_data: Optional[Dict],
                              x: int, y: int, width: int) -> int:
        """Draw comprehensive moon phase information at bottom."""
        # Always show moon section, even if no data
        # Moon header (large, centered)
        moon_title = "Moon Phase Information"
        title_bbox = draw.textbbox((0, 0), moon_title, font=self.fonts['h2'])
        title_width = title_bbox[2] - title_bbox[0]
        title_x = x + (width - title_width) // 2
        
        draw.text((title_x, y), moon_title, 
                 fill=self.colors['black'], font=self.fonts['h2'])
        y += 100
        
        if not moon_data:
            # Show message when no moon data available
            no_data_text = "Moon phase data unavailable"
            no_data_bbox = draw.textbbox((0, 0), no_data_text, font=self.fonts['body'])
            no_data_width = no_data_bbox[2] - no_data_bbox[0]
            no_data_x = x + (width - no_data_width) // 2
            
            draw.text((no_data_x, y), no_data_text, 
                     fill=self.colors['medium'], font=self.fonts['body'])
            return y + 60
        
        # Current illumination (large, centered)
        illumination = moon_data.get('current_illumination', 50)
        illum_text = f"Currently {illumination}% Illuminated"
        illum_bbox = draw.textbbox((0, 0), illum_text, font=self.fonts['body'])
        illum_width = illum_bbox[2] - illum_bbox[0]
        illum_x = x + (width - illum_width) // 2
        
        draw.text((illum_x, y), illum_text, 
                 fill=self.colors['dark'], font=self.fonts['body'])
        y += 80
        
        # Next phase (if available, centered)
        phases = moon_data.get('phases', [])
        if phases:
            next_phase = phases[0]
            phase_name = next_phase.get('phase', '')
            phase_date = next_phase.get('date', '')
            if phase_name and phase_date:
                phase_text = f"Next: {phase_name} on {phase_date}"
                phase_bbox = draw.textbbox((0, 0), phase_text, font=self.fonts['caption'])
                phase_width = phase_bbox[2] - phase_bbox[0]
                phase_x = x + (width - phase_width) // 2
                
                draw.text((phase_x, y), phase_text, 
                         fill=self.colors['medium'], font=self.fonts['caption'])
        
        return y + 60
    
    def _draw_detailed_weather_location(self, draw: ImageDraw.Draw, location_data: Optional[Dict],
                                       moon_data: Optional[Dict], x: int, y: int, width: int, location_type: str) -> int:
        """Draw comprehensive weather details for one location (XDA-style)."""
        # Draw border around the entire location section
        border_margin = 20
        border_x = x - border_margin
        border_width = width + (2 * border_margin)
        
        if not location_data or not location_data.get('weather'):
            # Error message
            error_text = "Weather unavailable"
            draw.text((x + 20, y + 100), error_text, 
                     fill=self.colors['medium'], font=self.fonts['body'])
            # Draw error border
            draw.rectangle([border_x, y - 10, border_x + border_width, y + 220], 
                          outline=self.colors['lighter'], width=3)
            return y + 200
        
        location_info = location_data.get('location_info', {})
        weather = location_data.get('weather', {})
        current = weather.get('current', {})
        daily = weather.get('daily', [])
        
        start_y = y
        current_y = y + 20  # Add padding inside border
        
        # Location name (large, centered)
        if location_type == "CURRENT":
            city = location_info.get('city', 'Unknown')
            country = location_info.get('country', '')
            location_text = f"{city}"
            if country:
                location_text += f", {country}"
        else:
            location_text = location_info.get('name', 'Jerusalem, Israel')
        
        # Center the location text
        location_bbox = draw.textbbox((0, 0), location_text, font=self.fonts['h2'])
        location_width = location_bbox[2] - location_bbox[0]
        location_x = x + (width - location_width) // 2
        
        draw.text((location_x, current_y), location_text, 
                 fill=self.colors['black'], font=self.fonts['h2'])
        current_y += 80
        
        # Current temperature (large) with time
        temp = current.get('temperature', 0)
        temp_unit = current.get('temperature_unit', '°F')
        temp_text = f"{temp:.0f}{temp_unit}"
        
        # Get current time for this location
        current_time = self._get_location_time(location_type)
        
        # Temperature and time side-by-side (centered as a group)
        temp_time_gap = 40
        
        # Calculate total width of temp + gap + time
        temp_bbox = draw.textbbox((0, 0), temp_text, font=self.fonts['hero'])
        temp_width = temp_bbox[2] - temp_bbox[0]
        time_bbox = draw.textbbox((0, 0), current_time, font=self.fonts['h2'])
        time_width = time_bbox[2] - time_bbox[0]
        
        total_width = temp_width + temp_time_gap + time_width
        start_x = x + (width - total_width) // 2
        
        # Draw temperature
        draw.text((start_x, current_y), temp_text, 
                 fill=self.colors['black'], font=self.fonts['hero'])
        
        # Draw time aligned to same baseline as temperature
        time_x = start_x + temp_width + temp_time_gap
        draw.text((time_x, current_y + 40), current_time, 
                 fill=self.colors['medium'], font=self.fonts['h2'])
        current_y += 160
        
        # Weather description with nice emoji and lunar phase (centered)
        description = current.get('description', 'Unknown')
        weather_emoji = self._get_weather_emoji(current.get('weathercode', 0))
        
        # Add lunar cycle status to the weather description
        lunar_status = ""
        if moon_data:
            illumination = moon_data.get('current_illumination', 50)
            phase_name = moon_data.get('current_phase', 'Unknown')
            # Get appropriate moon emoji based on phase
            moon_emoji = self._get_moon_emoji(phase_name)
            lunar_status = f" | {moon_emoji} {phase_name} ({illumination}%)"
        
        desc_text = f"{weather_emoji} {description}{lunar_status}"
        
        # Center weather description
        desc_bbox = draw.textbbox((0, 0), desc_text, font=self.fonts['h2'])
        desc_width = desc_bbox[2] - desc_bbox[0]
        desc_x = x + (width - desc_width) // 2
        
        draw.text((desc_x, current_y), desc_text, 
                 fill=self.colors['medium'], font=self.fonts['h2'])
        current_y += 100
        
        # Stats section with subtle border (wind, pressure, feels like)
        stats_start_y = current_y
        stats_border_margin = 10
        stats_border_x = x - stats_border_margin
        stats_border_width = width + (2 * stats_border_margin)
        
        current_y += 10  # Padding inside stats border
        
        # Wind speed (centered)
        wind_speed = current.get('windspeed', 0)
        wind_text = f"Wind: {wind_speed:.1f} mph"
        wind_bbox = draw.textbbox((0, 0), wind_text, font=self.fonts['h1'])
        wind_width = wind_bbox[2] - wind_bbox[0]
        wind_x = x + (width - wind_width) // 2
        
        draw.text((wind_x, current_y), wind_text, 
                 fill=self.colors['dark'], font=self.fonts['h1'])
        current_y += 120
        
        # Pressure (if available)
        pressure = current.get('surface_pressure', 0)
        if pressure > 0:
            pressure_text = f"Pressure: {pressure:.1f} hPa"
            pressure_bbox = draw.textbbox((0, 0), pressure_text, font=self.fonts['h1'])
            pressure_width = pressure_bbox[2] - pressure_bbox[0]
            pressure_x = x + (width - pressure_width) // 2
            draw.text((pressure_x, current_y), pressure_text, 
                     fill=self.colors['dark'], font=self.fonts['h1'])
            current_y += 120
        
        # Feels like temperature (centered)
        feels_like = current.get('apparent_temperature', temp)
        feels_like_text = f"Feels like: {feels_like:.0f}{temp_unit}"
        feels_bbox = draw.textbbox((0, 0), feels_like_text, font=self.fonts['h1'])
        feels_width = feels_bbox[2] - feels_bbox[0]
        feels_x = x + (width - feels_width) // 2
        
        draw.text((feels_x, current_y), feels_like_text, 
                 fill=self.colors['dark'], font=self.fonts['h1'])
        current_y += 120
        
        # Draw subtle stats section border (outline only)
        stats_height = current_y - stats_start_y + 10  # Add bottom padding
        draw.rectangle([stats_border_x, stats_start_y, 
                       stats_border_x + stats_border_width, 
                       stats_start_y + stats_height], 
                      outline=self.colors['light'], width=1)
        
        # 3-day forecast section - title INSIDE border at top
        current_y += 20  # Space before forecast section
        
        # Start the forecast border first
        forecast_start_y = current_y
        forecast_border_margin = 20
        forecast_border_x = x - forecast_border_margin
        forecast_border_width = width + (2 * forecast_border_margin)
        
        current_y += 20  # Padding inside forecast border
        
        # Draw title inside border at the top
        forecast_title = "3-Day Forecast"
        title_bbox = draw.textbbox((0, 0), forecast_title, font=self.fonts['h2'])
        title_width = title_bbox[2] - title_bbox[0]
        title_x = x + (width - title_width) // 2
        
        draw.text((title_x, current_y), forecast_title, 
                 fill=self.colors['black'], font=self.fonts['h2'])
        current_y += 140
        
        # Draw forecast horizontally (side by side) - 3 days with dates
        forecast_items = []
        from datetime import datetime, timedelta
        today = datetime.now()
        
        for i, day in enumerate(daily[:3]):  # Only 3 days
            # Calculate actual date
            forecast_date = today + timedelta(days=i+1)
            date_str = forecast_date.strftime("%m/%d")  # MM/DD format
            day_name = forecast_date.strftime("%a")  # Mon, Tue, etc
            
            max_temp = f"{day.get('max_temp', 0):.0f}°"
            min_temp = f"{day.get('min_temp', 0):.0f}°"
            # Remove weather codes/icons from forecast
            forecast_text = f"{day_name}\n{date_str}\n{max_temp}/{min_temp}"
            forecast_items.append(forecast_text)
        
        # Calculate positions for horizontal layout
        if forecast_items:
            item_width = width // len(forecast_items)
            for i, forecast_text in enumerate(forecast_items):
                item_x = x + (i * item_width) + (item_width // 2)
                # Center each forecast item within its allocated space
                item_bbox = draw.textbbox((0, 0), forecast_text.split('\n')[0], font=self.fonts['body'])
                item_text_width = item_bbox[2] - item_bbox[0]
                centered_x = item_x - (item_text_width // 2)
                
                # Draw each line of the forecast item with LARGER FONTS
                lines = forecast_text.split('\n')
                line_y = current_y
                for line in lines:
                    # Use h2 font (200pt) instead of body (120pt) for better readability
                    line_bbox = draw.textbbox((0, 0), line, font=self.fonts['h2'])
                    line_width = line_bbox[2] - line_bbox[0]
                    line_x = item_x - (line_width // 2)
                    
                    draw.text((line_x, line_y), line, 
                             fill=self.colors['medium'], font=self.fonts['h2'])
                    line_y += 120  # Increased spacing for larger font
            
            current_y += 380  # More space for larger forecast
        
        # Draw professional forecast section border (outline only)
        forecast_height = current_y - forecast_start_y + 20  # Add bottom padding
        draw.rectangle([forecast_border_x, forecast_start_y, 
                       forecast_border_x + forecast_border_width, 
                       forecast_start_y + forecast_height], 
                      outline=self.colors['medium'], width=2)
        
        # Moon phase (moved down and centered)
        if moon_data and current_y < self.height - 150:
            current_y += 60  # More space above moon
            illumination = moon_data.get('current_illumination', 50)
            phase_name = moon_data.get('current_phase', 'Unknown')
            moon_text = f"🌙 {illumination}% - {phase_name}"
            
            # Center the moon text
            moon_bbox = draw.textbbox((0, 0), moon_text, font=self.fonts['h2'])
            moon_width = moon_bbox[2] - moon_bbox[0]
            moon_x = x + (width - moon_width) // 2
            
            draw.text((moon_x, current_y), moon_text, 
                     fill=self.colors['dark'], font=self.fonts['h2'])
            current_y += 80  # Space after moon
        
        # Draw professional border around the entire location section (OUTLINE ONLY)
        border_height = current_y - start_y + 30  # Add bottom padding
        
        # Simple professional border - just outline, no fill
        draw.rectangle([border_x, start_y - 5, border_x + border_width, start_y + border_height], 
                      outline=self.colors['medium'], width=2)
        
        return current_y
    
    def _get_wind_direction(self, degrees: float) -> str:
        """Convert wind direction degrees to compass direction."""
        directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                     'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        index = round(degrees / 22.5) % 16
        return directions[index]
    
    def _get_location_time(self, location_type: str) -> str:
        """Get current time for a location based on its timezone."""
        try:
            if location_type == 'CURRENT':
                # Use local system timezone
                local_time = datetime.now()
                return local_time.strftime("%I:%M %p")
            elif location_type == 'SECOND' and ZoneInfo:
                # Use Jerusalem timezone for second location
                jerusalem_tz = ZoneInfo('Asia/Jerusalem')
                jerusalem_time = datetime.now(jerusalem_tz)
                return jerusalem_time.strftime("%I:%M %p")
            else:
                # Fallback to local time
                local_time = datetime.now()
                return local_time.strftime("%I:%M %p")
        except Exception as e:
            self.logger.warning(f"Error getting location time: {e}")
            # Fallback to local time
            local_time = datetime.now()
            return local_time.strftime("%I:%M %p")
    
    def _get_current_weather_page(self) -> int:
        """Get current page to display (0 or 1) based on 30-second rotation."""
        from datetime import datetime
        now = datetime.now()
        
        # Calculate seconds since midnight
        seconds_since_midnight = now.hour * 3600 + now.minute * 60 + now.second
        
        # 30-second rotation: 0-29 seconds = page 0, 30-59 seconds = page 1
        page_slot = (seconds_since_midnight // 30) % 2
        return page_slot
    
    def _draw_full_page_location(self, draw: ImageDraw.Draw, location_data: Optional[Dict],
                                moon_data: Optional[Dict], x: int, y: int, width: int, page_type: str) -> int:
        """Draw full-page weather display for one location."""
        if not location_data or not location_data.get('weather'):
            # Center error message
            error_text = "Weather data unavailable"
            error_bbox = draw.textbbox((0, 0), error_text, font=self.fonts['h1'])
            error_width = error_bbox[2] - error_bbox[0]
            error_x = x + (width - error_width) // 2
            error_y = y + self.height // 3
            
            draw.text((error_x, error_y), error_text, 
                     fill=self.colors['medium'], font=self.fonts['h1'])
            return error_y + 100
        
        location_info = location_data.get('location_info', {})
        weather = location_data.get('weather', {})
        current = weather.get('current', {})
        
        current_y = y
        
        # Location name (huge, centered)
        if page_type == "CURRENT":
            city = location_info.get('city', 'Unknown')
            country = location_info.get('country', '')
            location_text = f"{city}"
            if country:
                location_text += f", {country}"
        else:
            location_text = location_info.get('name', 'Jerusalem, Israel')
        
        location_bbox = draw.textbbox((0, 0), location_text, font=self.fonts['h1'])
        location_width = location_bbox[2] - location_bbox[0]
        location_x = x + (width - location_width) // 2
        
        draw.text((location_x, current_y), location_text, 
                 fill=self.colors['black'], font=self.fonts['h1'])
        current_y += 320  # Large spacing after location
        
        # Temperature (gigantic, centered)
        temp = current.get('temperature', 0)
        temp_unit = current.get('temperature_unit', '°F')
        temp_text = f"{temp:.0f}{temp_unit}"
        
        temp_bbox = draw.textbbox((0, 0), temp_text, font=self.fonts['hero'])
        temp_width = temp_bbox[2] - temp_bbox[0]
        temp_x = x + (width - temp_width) // 2
        
        draw.text((temp_x, current_y), temp_text, 
                 fill=self.colors['black'], font=self.fonts['hero'])
        current_y += 600  # Large spacing after temperature
        
        # Weather description (large, centered)
        description = current.get('description', 'Unknown')
        weather_icon = self._get_weather_icon_for_code(current.get('weathercode', 0))
        desc_text = f"{weather_icon} - {description}"
        
        desc_bbox = draw.textbbox((0, 0), desc_text, font=self.fonts['h2'])
        desc_width = desc_bbox[2] - desc_bbox[0]
        desc_x = x + (width - desc_width) // 2
        
        draw.text((desc_x, current_y), desc_text, 
                 fill=self.colors['medium'], font=self.fonts['h2'])
        current_y += 280
        
        # Temperature-based art (centered)
        temp_art = self._get_temperature_art(temp)
        if temp_art:
            art_lines = temp_art.split('\n')
            for line in art_lines:
                if line.strip():
                    line_bbox = draw.textbbox((0, 0), line, font=self.fonts['h3'])
                    line_width = line_bbox[2] - line_bbox[0]
                    line_x = x + (width - line_width) // 2
                    
                    draw.text((line_x, current_y), line, 
                             fill=self.colors['medium'], font=self.fonts['h3'])
                    current_y += 100  # Spacing between art lines
        
        current_y += 80
        
        # Moon phase info (centered at bottom)
        moon_y = self.height - 300
        self._draw_centered_moon_info(draw, moon_data, x, moon_y, width)
        
        return current_y
    
    def _draw_centered_moon_info(self, draw: ImageDraw.Draw, moon_data: Optional[Dict],
                                x: int, y: int, width: int) -> int:
        """Draw moon phase information centered at bottom of page."""
        # Moon header
        moon_title = "🌙 Moon Phase"
        title_bbox = draw.textbbox((0, 0), moon_title, font=self.fonts['h2'])
        title_width = title_bbox[2] - title_bbox[0]
        title_x = x + (width - title_width) // 2
        
        draw.text((title_x, y), moon_title, 
                 fill=self.colors['black'], font=self.fonts['h2'])
        y += 120
        
        if not moon_data:
            no_data_text = "Data unavailable"
            no_data_bbox = draw.textbbox((0, 0), no_data_text, font=self.fonts['body'])
            no_data_width = no_data_bbox[2] - no_data_bbox[0]
            no_data_x = x + (width - no_data_width) // 2
            
            draw.text((no_data_x, y), no_data_text, 
                     fill=self.colors['medium'], font=self.fonts['body'])
            return y + 80
        
        # Current illumination
        illumination = moon_data.get('current_illumination', 50)
        phase_name = moon_data.get('current_phase', 'Unknown')
        illum_text = f"{illumination}% Illuminated - {phase_name}"
        
        illum_bbox = draw.textbbox((0, 0), illum_text, font=self.fonts['body'])
        illum_width = illum_bbox[2] - illum_bbox[0]
        illum_x = x + (width - illum_width) // 2
        
        draw.text((illum_x, y), illum_text, 
                 fill=self.colors['dark'], font=self.fonts['body'])
        
        return y + 80
    
    def _draw_page_indicator(self, draw: ImageDraw.Draw, current_page: int):
        """Draw page indicator at bottom of screen."""
        indicator_y = self.height - 40
        indicator_text = f"● ○" if current_page == 0 else f"○ ●"
        
        # Center the indicator
        indicator_bbox = draw.textbbox((0, 0), indicator_text, font=self.fonts['caption'])
        indicator_width = indicator_bbox[2] - indicator_bbox[0]
        indicator_x = (self.width - indicator_width) // 2
        
        draw.text((indicator_x, indicator_y), indicator_text, 
                 fill=self.colors['medium'], font=self.fonts['caption'])
    
    def _get_temperature_art(self, temp: float) -> str:
        """Get fun ASCII art based on temperature."""
        if temp <= 20:  # Very cold (20°F and below)
            return """    ❄️  ❄️  ❄️
  ❄️      ❄️
❄️  COLD!  ❄️
  ❄️      ❄️
    ❄️  ❄️  ❄️"""
        elif temp <= 32:  # Freezing (21-32°F)
            return """  ⭐ FREEZING ⭐
    *  *  *
  *  ICE  *
    *  *  *"""
        elif temp <= 50:  # Cold (33-50°F)
            return """   🌨️ CHILLY 🌨️
  ·  ·  ·  ·
·    COLD    ·
  ·  ·  ·  ·"""
        elif temp <= 65:  # Cool (51-65°F)
            return """  🍂 COOL 🍂
 ~  ~  ~  ~
~  COMFY  ~
 ~  ~  ~  ~"""
        elif temp <= 75:  # Perfect (66-75°F)
            return """  🌤️ PERFECT! 🌤️
 ◇  ◇  ◇  ◇
◇   NICE   ◇
 ◇  ◇  ◇  ◇"""
        elif temp <= 85:  # Warm (76-85°F)
            return """  ☀️ WARM ☀️
 ·  ·  ·  ·
·  LOVELY  ·
 ·  ·  ·  ·"""
        elif temp <= 95:  # Hot (86-95°F)
            return """   🔥 HOT! 🔥
  ~~~~~~~~~~~
 ~ SIZZLING ~
  ~~~~~~~~~~~"""
        else:  # Very hot (96°F+)
            return """  🌡️ SCORCHING! 🌡️
 ▲▲▲▲▲▲▲▲▲▲▲
▲   BLAZING   ▲
 ▲▲▲▲▲▲▲▲▲▲▲"""


# Global modern weather display generator instance
modern_weather_display = ModernWeatherDisplay()