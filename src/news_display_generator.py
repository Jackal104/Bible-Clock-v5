"""
News Display Generator - Creates e-ink optimized news displays for Bible Clock.
Shows cycling Israel news with professional layout and large readable fonts.
"""

from PIL import Image, ImageDraw, ImageFont
import textwrap
import logging
from typing import Dict, Optional
from datetime import datetime
from news_service import news_service


class NewsDisplayGenerator:
    """Generates news displays optimized for e-ink screens."""
    
    def __init__(self, width: int = 1872, height: int = 1404, font_config: dict = None):
        self.width = width
        self.height = height
        self.logger = logging.getLogger(__name__)
        
        # Scale factor for different display sizes
        self.scale_factor = min(self.width / 1872, self.height / 1404)
        
        # Colors optimized for e-ink - use pure black for better contrast
        self.colors = {
            'black': 0,           # Pure black for all text (better e-ink contrast)
            'dark': 0,            # Use pure black instead of gray for better readability
            'medium': 0,          # Use pure black instead of gray for better readability  
            'light': 128,         # Light gray for subtle elements only
            'lighter': 192,       # Very light gray for backgrounds
            'white': 255          # Pure white for backgrounds
        }
        
        # Get font sizes from config or use smaller defaults
        if font_config:
            title_size = font_config.get('title_font_size', 48)
            verse_size = font_config.get('verse_font_size', 80)  
            reference_size = font_config.get('reference_font_size', 84)
        else:
            title_size = 48
            verse_size = 80
            reference_size = 84
        
        # Font configuration - Large, readable news layout with bigger time display
        self.fonts = {
            'hero': self._load_font(int(reference_size * 0.7)),      # Article indicator
            'h1': self._load_font(int(verse_size * 1.2)),            # Main headline - MUCH LARGER
            'h2': self._load_font(int(reference_size * 0.9)),        # Time display - LARGER
            'h3': self._load_font(int(title_size * 0.9)),            # Section headers
            'body': self._load_font(int(verse_size * 1.0)),          # Article text - MUCH LARGER
            'caption': self._load_font(int(title_size * 0.8)),       # Metadata
            'micro': self._load_font(int(title_size * 0.7))          # Small details
        }
    
    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Load system font with fallback and better hinting for sharper text."""
        try:
            # Use the regular DejaVu Sans font for better e-ink rendering
            # Bold fonts can appear fuzzy on e-ink displays
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except:
            try:
                # Try system font alternatives
                return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", size)
            except:
                try:
                    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
                except:
                    return ImageFont.load_default()
    
    def generate_news_display(self) -> Image.Image:
        """Generate the main news display with memory management."""
        import gc
        
        try:
            # Force garbage collection before generation
            gc.collect()
            
            # Get current article to display
            article = news_service.get_current_article()
            
            if not article:
                image = self._create_no_news_display()
            else:
                image = self._create_article_display(article)
            
            # Force garbage collection after generation
            gc.collect()
            
            # Log memory usage after generation
            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                self.logger.info(f"News display memory after generation: {memory_mb:.1f}MB")
            except:
                pass  # Don't fail if psutil unavailable
            
            return image
            
        except Exception as e:
            self.logger.error(f"Error generating news display: {e}")
            gc.collect()  # Cleanup on error too
            return self._create_error_display(str(e))
    
    def _create_article_display(self, article: Dict) -> Image.Image:
        """Create display for a single news article."""
        image = self._create_background()
        draw = ImageDraw.Draw(image)
        
        current_y = 55  # Start even lower for better positioning
        margin = 15  # Even smaller margin for maximum text width  
        content_width = self.width - (2 * margin)  # Maximum usable width
        
        # Header with Israel News title
        current_y = self._draw_header(draw, current_y, margin, content_width)
        current_y += 40  # Even more spacing after header
        
        # Article indicator (which article of total)
        all_articles = news_service.get_israel_news()
        article_num = news_service.current_article_index + 1
        total_articles = len(all_articles)
        current_y = self._draw_article_indicator(draw, current_y, margin, content_width, article_num, total_articles)
        current_y += 45  # Much more spacing after indicator to push content down much further
        
        # Main article content
        current_y = self._draw_article_content(draw, article, current_y, margin, content_width)
        
        # Footer with update info
        self._draw_footer(draw, article.get('published_str', ''))
        
        return image
    
    def _get_last_friday_of_march(self, year: int) -> datetime.date:
        """Get the last Friday of March for DST calculation."""
        from calendar import monthrange
        last_day = monthrange(year, 3)[1]
        last_date = datetime(year, 3, last_day).date()
        
        # Find the last Friday (weekday 4)
        days_back = (last_date.weekday() - 4) % 7
        return datetime(year, 3, last_day - days_back).date()
    
    def _get_last_sunday_of_october(self, year: int) -> datetime.date:
        """Get the last Sunday of October for DST calculation."""
        from calendar import monthrange
        last_day = monthrange(year, 10)[1]
        last_date = datetime(year, 10, last_day).date()
        
        # Find the last Sunday (weekday 6)
        days_back = (last_date.weekday() - 6) % 7
        return datetime(year, 10, last_day - days_back).date()
    
    def _draw_header(self, draw: ImageDraw.Draw, y: int, x: int, width: int) -> int:
        """Draw the Israel News header with current time and Israel time."""
        from datetime import timezone, timedelta
        
        # Get current local time and date
        local_now = datetime.now()
        local_time = local_now.strftime("%I:%M %p")
        local_date = local_now.strftime("%m/%d/%Y")
        
        # Get Israel time - Israel is UTC+2 in winter, UTC+3 in summer (DST)
        # Israel DST runs from last Friday in March to last Sunday in October
        now_utc = datetime.now(timezone.utc)
        
        # Check if Israel is in DST (simplified check)
        year = now_utc.year
        march_last_friday = self._get_last_friday_of_march(year)
        october_last_sunday = self._get_last_sunday_of_october(year)
        
        if march_last_friday <= now_utc.date() <= october_last_sunday:
            israel_offset = 3  # DST
        else:
            israel_offset = 2  # Standard time
            
        israel_tz = timezone(timedelta(hours=israel_offset))
        israel_now = now_utc.astimezone(israel_tz)
        israel_time = israel_now.strftime("%I:%M %p")
        israel_date = israel_now.strftime("%m/%d/%Y")
        
        # Create header components with date and time
        israel_time_text = f"Israel: {israel_time}\n{israel_date}"
        main_title = "✡️ ISRAEL NEWS ✡️"
        local_time_text = f"Local: {local_time}\n{local_date}"
        
        # Calculate positions for three-part layout
        # Get bounding boxes for single-line text to determine heights
        single_line_bbox = draw.textbbox((0, 0), "Sample", font=self.fonts['h2'])
        side_text_height = (single_line_bbox[3] - single_line_bbox[1]) * 2 + 5  # Two lines + small gap
        
        title_bbox = draw.textbbox((0, 0), main_title, font=self.fonts['h1'])
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        
        # Center main title vertically with the side text
        title_x = x + (width - title_width) // 2
        title_y = y + (side_text_height - title_height) // 2
        
        # Position Israel time/date on left (align top with title area)
        israel_x = x + 20
        israel_y = y
        
        # Position local time/date on right (align top with title area)
        # Calculate right alignment for multi-line text
        israel_lines = israel_time_text.split('\n')
        local_lines = local_time_text.split('\n')
        
        # Get width of longest line for right alignment
        local_line1_bbox = draw.textbbox((0, 0), local_lines[0], font=self.fonts['h2'])
        local_line2_bbox = draw.textbbox((0, 0), local_lines[1], font=self.fonts['h2'])
        max_local_width = max(local_line1_bbox[2] - local_line1_bbox[0], 
                             local_line2_bbox[2] - local_line2_bbox[0])
        local_x = x + width - max_local_width - 20
        local_y = y
        
        # Draw Israel time and date (left side)
        line_height = single_line_bbox[3] - single_line_bbox[1] + 5
        for i, line in enumerate(israel_lines):
            current_y = israel_y + (i * line_height)
            # Use pure black text without shadow for better e-ink contrast
            draw.text((israel_x, current_y), line, fill=self.colors['black'], font=self.fonts['h2'])
        
        # Draw main title (center) with shadow effect
        # Use pure black text without shadow for better e-ink contrast
        draw.text((title_x, title_y), main_title, fill=self.colors['black'], font=self.fonts['h1'])
        
        # Draw local time and date (right side, right-aligned)
        for i, line in enumerate(local_lines):
            line_bbox = draw.textbbox((0, 0), line, font=self.fonts['h2'])
            line_width = line_bbox[2] - line_bbox[0]
            line_x = x + width - line_width - 20  # Right align each line individually
            current_y = local_y + (i * line_height)
            # Use pure black text without shadow for better e-ink contrast
            draw.text((line_x, current_y), line, fill=self.colors['black'], font=self.fonts['h2'])
        
        # Underline
        header_bottom = y + max(side_text_height, title_height)
        line_y = header_bottom + 20
        line_margin = 60
        draw.line([(x + line_margin, line_y), (x + width - line_margin, line_y)], 
                 fill=self.colors['medium'], width=3)
        
        return line_y + 20
    
    def _draw_article_indicator(self, draw: ImageDraw.Draw, y: int, x: int, width: int, 
                               article_num: int, total: int) -> int:
        """Draw article number indicator."""
        indicator_text = f"Article {article_num} of {total}"
        indicator_bbox = draw.textbbox((0, 0), indicator_text, font=self.fonts['h2'])
        indicator_width = indicator_bbox[2] - indicator_bbox[0]
        indicator_x = x + (width - indicator_width) // 2
        
        draw.text((indicator_x, y), indicator_text, 
                 fill=self.colors['medium'], font=self.fonts['h2'])
        
        return y + indicator_bbox[3] - indicator_bbox[1]
    
    def _draw_article_content(self, draw: ImageDraw.Draw, article: Dict, y: int, x: int, width: int) -> int:
        """Draw the main article content with full-width title, content, and bottom metadata."""
        current_y = y
        
        # 1. Article title (headline) - CENTERED with optimized wrapping and spacing
        title = article.get('title', 'No title')
        current_y = self._draw_optimized_title(draw, title, x, current_y, width)
        current_y += 50  # Even more space after title for better visual separation
        
        # 2. Article description/content - FULL WIDTH under title with optimized padding
        description = article.get('description', '')
        if description:
            # Add subtle border around content with minimal padding
            content_start_y = current_y
            border_margin = 10  # Minimal border margins
            border_x = x - border_margin
            border_width = width + (2 * border_margin)
            
            content_y = current_y + 25  # Increased padding for more vertical space
            
            content_end_y = self._draw_wrapped_text(draw, description, x, content_y, width,
                                              self.fonts['body'], self.colors['black'], line_spacing=18)
            content_end_y += 25  # Increased bottom padding for more vertical space
            
            # Draw subtle border around content
            border_height = content_end_y - content_start_y
            draw.rectangle([border_x, content_start_y, border_x + border_width, content_start_y + border_height],
                          outline=self.colors['light'], width=2)
            
            current_y = content_end_y + 60  # Extra space since no metadata box
        else:
            current_y += 60  # Extra space since no metadata box
        
        # 3. Publication metadata - FULL WIDTH at bottom
        source = article.get('source', 'Unknown Source')
        published = article.get('published_str', '')
        age_hours = article.get('age_hours', 0)
        
        if age_hours < 1:
            age_text = "Just now"
        elif age_hours < 24:
            age_text = f"{age_hours}h ago"
        else:
            age_text = f"{age_hours // 24}d ago"
        
        # Store metadata for footer - remove the prominent metadata box
        # Metadata will be integrated into the footer instead
        self.current_source = source
        self.current_published = published
        self.current_age_text = age_text
        
        return current_y
    
    def _draw_optimized_title(self, draw: ImageDraw.Draw, title: str, x: int, y: int, width: int) -> int:
        """Draw title with optimized text wrapping to fit maximum words per line."""
        if not title.strip():
            return y
            
        font = self.fonts['h1']
        color = self.colors['black']
        line_spacing = 25
        
        # Use the same optimized character width calculation as body text
        sample_text = "The quick brown fox jumps over lazy dogs with 1234567890"
        test_bbox = draw.textbbox((0, 0), sample_text, font=font)
        char_width = (test_bbox[2] - test_bbox[0]) / len(sample_text)
        chars_per_line = int(width / char_width * 0.96)  # 96% - aggressive fitting
        
        # Use optimized text wrapping for maximum words per line
        wrapped_lines = textwrap.wrap(title, width=chars_per_line, break_long_words=False, 
                                     break_on_hyphens=False, expand_tabs=False)
        
        current_y = y
        for line in wrapped_lines:
            # Center the title text
            line_bbox = draw.textbbox((0, 0), line, font=font)
            line_width = line_bbox[2] - line_bbox[0]
            line_x = x + (width - line_width) // 2  # Center horizontally
            
            # Draw centered title text
            draw.text((line_x, current_y), line, fill=color, font=font)
            
            # Get actual line height from the specific text
            line_height = line_bbox[3] - line_bbox[1]
            current_y += line_height + line_spacing
        
        return current_y
    
    def _draw_wrapped_text(self, draw: ImageDraw.Draw, text: str, x: int, y: int, width: int,
                          font: ImageFont.FreeTypeFont, color: int, line_spacing: int = 10) -> int:
        """Draw text with word wrapping and better character estimation for sharp rendering."""
        if not text.strip():
            return y
        
        # Optimized character width calculation to fit maximum words per line
        # Use a more representative sample for accurate width calculation
        sample_text = "The quick brown fox jumps over lazy dogs with 1234567890"
        test_bbox = draw.textbbox((0, 0), sample_text, font=font)
        char_width = (test_bbox[2] - test_bbox[0]) / len(sample_text)
        chars_per_line = int(width / char_width * 0.96)  # 96% - more aggressive to fit more words
        
        # Use optimized text wrapping to maximize words per line
        wrapped_lines = textwrap.wrap(text, width=chars_per_line, break_long_words=False, 
                                     break_on_hyphens=False, expand_tabs=False)
        
        current_y = y
        for line in wrapped_lines:
            # Center the body text
            line_bbox = draw.textbbox((0, 0), line, font=font)
            line_width = line_bbox[2] - line_bbox[0]
            line_x = x + (width - line_width) // 2  # Center horizontally
            
            # Draw centered text
            draw.text((line_x, current_y), line, fill=color, font=font)
            
            # Get actual line height from the specific text
            line_height = line_bbox[3] - line_bbox[1]
            current_y += line_height + line_spacing
        
        return current_y
    
    def _draw_footer(self, draw: ImageDraw.Draw, last_update: str):
        """Draw footer with update and metadata information."""
        footer_y = self.height - 140  # Move up slightly to accommodate more info
        
        # Combine metadata with refresh information
        source = getattr(self, 'current_source', 'Unknown Source')
        published = getattr(self, 'current_published', '')
        age_text = getattr(self, 'current_age_text', '')
        
        # Create comprehensive footer with metadata and refresh info
        footer_text = f"📰 {source}  •  📅 {published}  •  ⏰ {age_text}  •  Articles cycle every 30s  •  Fresh news every 30min"
        
        # Use larger font for better readability in footer
        footer_font = self.fonts['h3']  # Larger than caption
        
        # Center footer text
        footer_bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
        footer_width = footer_bbox[2] - footer_bbox[0]
        footer_x = (self.width - footer_width) // 2
        
        draw.text((footer_x, footer_y), footer_text, 
                 fill=self.colors['medium'], font=footer_font)
    
    def _create_background(self) -> Image.Image:
        """Create background with minimal gradient for memory efficiency."""
        image = Image.new('L', (self.width, self.height), self.colors['white'])
        draw = ImageDraw.Draw(image)
        
        # Very minimal gradient to reduce memory usage
        gradient_steps = 10  # Further reduced from 20 steps
        step_height = self.height // gradient_steps
        
        for i in range(gradient_steps):
            y_start = i * step_height
            y_end = min((i + 1) * step_height, self.height)
            gradient_factor = i / gradient_steps
            color_value = int(self.colors['white'] - (gradient_factor * 3))  # Reduced gradient intensity
            draw.rectangle([(0, y_start), (self.width, y_end)], fill=color_value)
        
        # Clean up draw object
        del draw
        
        return image
    
    def _create_no_news_display(self) -> Image.Image:
        """Create display when no news is available."""
        image = self._create_background()
        draw = ImageDraw.Draw(image)
        
        # Center message
        message = "No Israel News Available"
        subtitle = "Checking for updates..."
        
        message_bbox = draw.textbbox((0, 0), message, font=self.fonts['h1'])
        message_width = message_bbox[2] - message_bbox[0]
        message_x = (self.width - message_width) // 2
        message_y = self.height // 2 - 100
        
        draw.text((message_x, message_y), message, 
                 fill=self.colors['dark'], font=self.fonts['h1'])
        
        subtitle_bbox = draw.textbbox((0, 0), subtitle, font=self.fonts['h2'])
        subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
        subtitle_x = (self.width - subtitle_width) // 2
        subtitle_y = message_y + 120
        
        draw.text((subtitle_x, subtitle_y), subtitle, 
                 fill=self.colors['medium'], font=self.fonts['h2'])
        
        return image
    
    def _create_error_display(self, error_message: str) -> Image.Image:
        """Create error display."""
        image = self._create_background()
        draw = ImageDraw.Draw(image)
        
        # Center error message
        error_title = "News Service Error"
        
        title_bbox = draw.textbbox((0, 0), error_title, font=self.fonts['h1'])
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (self.width - title_width) // 2
        title_y = self.height // 2 - 100
        
        draw.text((title_x, title_y), error_title, 
                 fill=self.colors['dark'], font=self.fonts['h1'])
        
        # Error details
        error_y = title_y + 120
        self._draw_wrapped_text(draw, error_message, 100, error_y, self.width - 200,
                               self.fonts['body'], self.colors['medium'])
        
        return image


# Create global instance
news_display_generator = NewsDisplayGenerator()