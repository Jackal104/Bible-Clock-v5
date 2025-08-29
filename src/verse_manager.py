"""
Manages Bible verse retrieval and scheduling.
"""

import json
import random
import requests
import logging
from datetime import datetime, time, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import os
import calendar
from error_log_manager import error_log_manager

class VerseManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_url = os.getenv('BIBLE_API_URL', 'https://bible-api.com')
        self.translation = os.getenv('DEFAULT_TRANSLATION', 'kjv')
        self.timeout = int(os.getenv('REQUEST_TIMEOUT', '10'))
        
        # Initialize devotional manager
        try:
            from src.devotional_manager import DevotionalManager
            self.devotional_manager = DevotionalManager()
            self.logger.info("Devotional manager initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize devotional manager: {e}")
            error_log_manager.log_error('verse_manager', 'devotional_init_failure', 
                                      f"Failed to initialize devotional manager: {e}", exception=e)
            self.devotional_manager = None
        
        # Multiple API support for different translations
        self.esv_api_key = os.getenv('ESV_API_KEY', '')  # From https://api.esv.org
        self.scripture_api_key = os.getenv('SCRIPTURE_API_KEY', '')  # From https://scripture.api.bible
        self.biblegateway_username = os.getenv('BIBLEGATEWAY_USERNAME', '')  # Bible Gateway username
        self.biblegateway_password = os.getenv('BIBLEGATEWAY_PASSWORD', '')  # Bible Gateway password
        self.biblegateway_token = None  # Will be obtained dynamically
        self.supported_translations = {
            # Primary translation - bible-api.com (free, no API key needed)
            'kjv': {'api': 'bible-api', 'code': 'kjv'},
            # ESV API (requires API key from https://api.esv.org)
            'esv': {'api': 'esv', 'code': 'esv'},
            # Bible Gateway API translations (requires username/password from https://www.biblegateway.com)
            'amp': {'api': 'biblegateway', 'code': 'AMP', 'name': 'Amplified Bible'},
            'nlt': {'api': 'biblegateway', 'code': 'NLT', 'name': 'New Living Translation'},
            'msg': {'api': 'biblegateway', 'code': 'MSG', 'name': 'The Message'},
            'nasb': {'api': 'biblegateway', 'code': 'NASB1995', 'name': 'New American Standard Bible 1995'},
            'cev': {'api': 'biblegateway', 'code': 'CEV', 'name': 'Contemporary English Version'}
        }
        
        # Enhanced features - use default mode from environment or fallback to time
        default_mode = os.getenv('DEFAULT_DISPLAY_MODE', 'time').lower()
        valid_modes = ['time', 'date', 'random', 'devotional', 'weather', 'news']
        
        # Handle parallel as a special case - it's time mode with parallel enabled
        if default_mode == 'parallel':
            self.display_mode = 'time'
            self.parallel_mode = True  # Enable parallel mode for time mode
        else:
            self.display_mode = default_mode if default_mode in valid_modes else 'time'
            self.parallel_mode = False  # Parallel mode off by default - user can enable
        self.secondary_translation = 'amp'  # Default secondary translation when parallel mode enabled
        
        # Track configured translations (may include "random") separately from working translations
        self._configured_translation = self.translation  # User's configured primary translation
        self._configured_secondary_translation = self.secondary_translation  # User's configured secondary translation
        self.time_format = '12'  # '12' for 12-hour format, '24' for 24-hour format
        # Memory optimization settings
        self.MAX_DAILY_ACTIVITY_DAYS = 30  # Keep only last 30 days
        self.MAX_BOOKS_ACCESSED = 50  # Limit books accessed tracking
        self.MAX_TRANSLATION_USAGE = 20  # Limit translation usage tracking
        # Enhanced statistics storage limits (NEW - only for visualization data)
        self.MAX_DETAILED_HISTORY = 1000     # Keep last 1000 verse entries for charts
        self.MAX_BOOK_BREAKDOWN_BOOKS = 100  # Maximum books in chapter breakdown
        self.MAX_MONTHLY_STATS = 24  # Keep 24 months of stats (2 years)
        self.MAX_YEARLY_STATS = 10   # Keep 10 years of stats
        self.last_recorded_minute = None     # Track last minute we recorded a verse
        
        # Book summary pagination tracking
        self.current_book_summary = None  # Store current book summary for pagination
        self.book_summary_minute = None  # Track which minute the book summary started
        
        self.statistics = {
            'verses_displayed': 0,
            'verses_today': 0,
            'books_accessed': set(),
            'translation_usage': {},
            'translation_failures': {},  # Track failed translation attempts
            'mode_usage': {'time': 0, 'date': 0, 'random': 0, 'devotional': 0, 'news': 0, 'parallel': 0},
            'daily_activity': {},  # Date -> count mapping for rotation
            # Enhanced statistics for detailed tracking
            'detailed_verse_history': [],  # List of {date, book, chapter, verse, translation, mode}
            'book_chapter_breakdown': {},  # book -> {chapter -> verse_count, total}
            'monthly_stats': {},  # YYYY-MM -> verse_count  
            'yearly_stats': {},   # YYYY -> verse_count
            # Daily cache tracking
            'verses_cached_today': 0,  # Count of verses cached today
            'cache_daily_reset': datetime.now().date()  # Track when to reset daily count
        }
        self.start_time = datetime.now()
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Load local data
        self._load_fallback_verses()
        self._load_book_summaries()
        self._load_kjv_bible()
        self._load_amp_bible()
        self._load_all_translation_caches()
        self._load_biblical_calendar()
        self._load_bible_structure()
        
        # All available Bible books (must be populated before completion calculation)
        self.available_books = []
        self._populate_available_books()
        
        # Verse caching system for building complete translations
        self.translation_cache_enabled = True
        self.translation_completion = self._calculate_all_translation_completion()
        self.logger.info(f"Translation cache completion: {self._format_completion_summary()}")
    
    def _load_fallback_verses(self):
        """Load fallback verses from JSON file."""
        try:
            fallback_path = Path('data/fallback_verses.json')
            with open(fallback_path, 'r') as f:
                self.fallback_verses = json.load(f)
            self.logger.info(f"Loaded {len(self.fallback_verses)} fallback verses")
        except Exception as e:
            self.logger.error(f"Failed to load fallback verses: {e}")
            self.fallback_verses = self._get_default_fallback_verses()
    
    def _load_book_summaries(self):
        """Load book summaries from JSON file."""
        try:
            summaries_path = Path('data/bible_book_summaries_kjv_all_66.json')
            with open(summaries_path, 'r') as f:
                self.book_summaries = json.load(f)
            self.logger.info(f"Loaded {len(self.book_summaries)} book summaries")
        except Exception as e:
            self.logger.error(f"Failed to load book summaries: {e}")
            self.book_summaries = {}
    
    def _load_kjv_bible(self):
        """Load complete KJV Bible for offline use."""
        try:
            kjv_path = Path('data/translations/bible_kjv.json')
            with open(kjv_path, 'r') as f:
                self.kjv_bible = json.load(f)
            self.logger.info("Loaded complete KJV Bible")
        except Exception as e:
            self.logger.error(f"Failed to load KJV Bible: {e}")
            self.kjv_bible = {}
    
    def _load_amp_bible(self):
        """Load complete AMP Bible for offline use."""
        try:
            amp_path = Path('data/translations/bible_amp.json')
            with open(amp_path, 'r') as f:
                self.amp_bible = json.load(f)
            self.logger.info("Loaded complete AMP Bible")
        except Exception as e:
            self.logger.warning(f"AMP Bible not found: {e}. Will use API or fallback methods.")
            self.amp_bible = {}
    
    def _load_all_translation_caches(self):
        """Load all cached translation files."""
        try:
            # Initialize translation caches dictionary
            self.translation_caches = {}
            
            # List of supported translations that can be cached
            cacheable_translations = ['kjv', 'esv', 'amp', 'nlt', 'msg', 'nasb']
            
            for translation in cacheable_translations:
                # Handle special case for NASB which uses nasb1995 file
                file_name = translation
                if translation == 'nasb':
                    file_name = 'nasb1995'
                
                cache_path = Path(f'data/translations/bible_{file_name}.json')
                try:
                    if cache_path.exists():
                        with open(cache_path, 'r') as f:
                            self.translation_caches[translation] = json.load(f)
                        self.logger.debug(f"Loaded {translation.upper()} translation cache from {file_name}")
                    else:
                        self.translation_caches[translation] = {}
                        self.logger.debug(f"Initialized empty cache for {translation.upper()}")
                except Exception as e:
                    self.logger.warning(f"Failed to load {translation} cache: {e}")
                    self.translation_caches[translation] = {}
            
            self.logger.info(f"Loaded translation caches for {len(self.translation_caches)} translations")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize translation caches: {e}")
            self.translation_caches = {}
    
    def _load_biblical_calendar(self):
        """Load biblical events calendar."""
        try:
            calendar_path = Path('data/biblical_events_calendar.json')
            if calendar_path.exists():
                with open(calendar_path, 'r') as f:
                    calendar_data = json.load(f)
                    self.biblical_events_calendar = calendar_data['biblical_events_calendar']
                self.logger.info(f"Loaded biblical events calendar with events, weekly, monthly, and seasonal themes")
            else:
                self.biblical_events_calendar = self._get_default_biblical_calendar()
            
            # Also keep old calendar for backward compatibility
            try:
                old_calendar_path = Path('data/biblical_calendar.json')
                if old_calendar_path.exists():
                    with open(old_calendar_path, 'r') as f:
                        self.biblical_calendar = json.load(f)
                else:
                    self.biblical_calendar = {}
            except:
                self.biblical_calendar = {}
                
        except Exception as e:
            self.logger.error(f"Failed to load biblical calendar: {e}")
            self.biblical_events_calendar = self._get_default_biblical_calendar()
            self.biblical_calendar = {}
    
    def _load_bible_structure(self):
        """Load complete Bible structure with chapter/verse counts."""
        try:
            structure_path = Path('data/bible_structure.json')
            with open(structure_path, 'r') as f:
                self.bible_structure = json.load(f)
            self.logger.info("Loaded complete Bible structure data")
        except Exception as e:
            self.logger.error(f"Failed to load Bible structure: {e}")
            self.bible_structure = {}
    
    def _populate_available_books(self):
        """Populate the list of available books from local KJV data."""
        # Always use the full list of Bible books for time-based calculations
        # Local KJV data is used for actual verse text when available
        self.available_books = [
            'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy',
            'Joshua', 'Judges', 'Ruth', '1 Samuel', '2 Samuel',
            '1 Kings', '2 Kings', '1 Chronicles', '2 Chronicles',
            'Ezra', 'Nehemiah', 'Esther', 'Job', 'Psalms', 'Proverbs',
            'Ecclesiastes', 'Song of Solomon', 'Isaiah', 'Jeremiah',
            'Lamentations', 'Ezekiel', 'Daniel', 'Hosea', 'Joel',
            'Amos', 'Obadiah', 'Jonah', 'Micah', 'Nahum', 'Habakkuk',
            'Zephaniah', 'Haggai', 'Zechariah', 'Malachi',
            'Matthew', 'Mark', 'Luke', 'John', 'Acts', 'Romans',
            '1 Corinthians', '2 Corinthians', 'Galatians', 'Ephesians',
            'Philippians', 'Colossians', '1 Thessalonians', '2 Thessalonians',
            '1 Timothy', '2 Timothy', 'Titus', 'Philemon', 'Hebrews',
            'James', '1 Peter', '2 Peter', '1 John', '2 John', '3 John',
            'Jude', 'Revelation'
        ]
        
        self.logger.info(f"Available books: {len(self.available_books)}")
    
    def _get_books_with_chapter(self, chapter_num: int) -> list:
        """Get list of books that have the specified chapter number."""
        books_with_chapter = []
        
        for book in self.available_books:
            if self.kjv_bible and book in self.kjv_bible:
                # Check local KJV data first
                book_data = self.kjv_bible[book]
                if str(chapter_num) in book_data:
                    books_with_chapter.append(book)
                # If not in local data, use estimates (local data is incomplete)
                elif self._book_likely_has_chapter(book, chapter_num):
                    books_with_chapter.append(book)
            else:
                # For books not in local data, make educated guesses
                if self._book_likely_has_chapter(book, chapter_num):
                    books_with_chapter.append(book)
        
        return books_with_chapter
    
    def _book_likely_has_chapter(self, book: str, chapter_num: int) -> bool:
        """Estimate if a book likely has the given chapter (fallback method)."""
        # Accurate chapter counts for all Bible books
        book_chapter_estimates = {
            # Old Testament
            'Genesis': 50, 'Exodus': 40, 'Leviticus': 27, 'Numbers': 36, 'Deuteronomy': 34,
            'Joshua': 24, 'Judges': 21, 'Ruth': 4, '1 Samuel': 31, '2 Samuel': 24,
            '1 Kings': 22, '2 Kings': 25, '1 Chronicles': 29, '2 Chronicles': 36,
            'Ezra': 10, 'Nehemiah': 13, 'Esther': 10, 'Job': 42, 'Psalms': 150, 'Proverbs': 31,
            'Ecclesiastes': 12, 'Song of Solomon': 8, 'Isaiah': 66, 'Jeremiah': 52,
            'Lamentations': 5, 'Ezekiel': 48, 'Daniel': 12, 'Hosea': 14, 'Joel': 3,
            'Amos': 9, 'Obadiah': 1, 'Jonah': 4, 'Micah': 7, 'Nahum': 3, 'Habakkuk': 3,
            'Zephaniah': 3, 'Haggai': 2, 'Zechariah': 14, 'Malachi': 4,
            # New Testament  
            'Matthew': 28, 'Mark': 16, 'Luke': 24, 'John': 21, 'Acts': 28, 'Romans': 16,
            '1 Corinthians': 16, '2 Corinthians': 13, 'Galatians': 6, 'Ephesians': 6,
            'Philippians': 4, 'Colossians': 4, '1 Thessalonians': 5, '2 Thessalonians': 3,
            '1 Timothy': 6, '2 Timothy': 4, 'Titus': 3, 'Philemon': 1, 'Hebrews': 13,
            'James': 5, '1 Peter': 5, '2 Peter': 3, '1 John': 5, '2 John': 1, '3 John': 1,
            'Jude': 1, 'Revelation': 22
        }
        
        estimated_chapters = book_chapter_estimates.get(book, 5)  # Conservative default
        return chapter_num <= estimated_chapters
    
    def _validate_verse_number(self, book: str, chapter: int, verse: int) -> Optional[int]:
        """Validate and adjust verse number using comprehensive Bible structure data."""
        try:
            # Use the complete Bible structure data
            max_verse = self._get_max_verse_for_chapter(book, chapter)
            
            if max_verse is None:
                self.logger.debug(f"No verse data found for {book} {chapter}")
                return None
            
            if verse <= max_verse:
                return verse
            else:
                # Don't adjust - return None to trigger book summary for invalid verse numbers
                self.logger.debug(f"Requested verse {verse} > max {max_verse} for {book} {chapter}, will show book summary")
                return None
                
        except Exception as e:
            self.logger.debug(f"Verse validation failed for {book} {chapter}:{verse}: {e}")
            return None
    
    def _get_max_verse_for_chapter(self, book: str, chapter: int) -> Optional[int]:
        """Get the maximum verse number for a given book and chapter using complete Bible data."""
        # First check our comprehensive loaded structure
        if hasattr(self, 'bible_structure') and self.bible_structure:
            if book in self.bible_structure:
                book_data = self.bible_structure[book]
                if str(chapter) in book_data:
                    return book_data[str(chapter)]
        
        # Fallback: check local KJV data if available
        if self.kjv_bible and book in self.kjv_bible:
            chapter_data = self.kjv_bible[book].get(str(chapter), {})
            if chapter_data:
                available_verses = [int(v) for v in chapter_data.keys() if v.isdigit()]
                if available_verses:
                    return max(available_verses)
        
        # No data found for this book/chapter
        return None
    
    def _get_all_books_with_valid_verse(self, chapter: int, verse: int) -> List[Dict]:
        """Get all books that have a valid verse for the given chapter:verse, with actual verse numbers."""
        candidate_books = []
        
        # Check all 66 Bible books systematically
        for book in self.available_books:
            # Check if this book has the requested chapter
            if not self._book_has_chapter(book, chapter):
                continue
            
            # Validate and get the actual verse number
            validated_verse = self._validate_verse_number(book, chapter, verse)
            if validated_verse:
                candidate_books.append({
                    'book': book,
                    'verse': validated_verse,
                    'exact_match': validated_verse == verse
                })
        
        # Sort to prioritize exact matches, then by book order
        candidate_books.sort(key=lambda x: (not x['exact_match'], self.available_books.index(x['book'])))
        
        return candidate_books
    
    def _book_has_chapter(self, book: str, chapter: int) -> bool:
        """Check if a book has the specified chapter."""
        if hasattr(self, 'bible_structure') and self.bible_structure:
            if book in self.bible_structure:
                return str(chapter) in self.bible_structure[book]
        
        # Fallback to estimates
        return self._book_likely_has_chapter(book, chapter)
    
    def _get_default_fallback_verses(self) -> List[Dict]:
        """Return default fallback verses if file loading fails."""
        return [
            {
                "reference": "John 3:16",
                "text": "For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.",
                "book": "John",
                "chapter": 3,
                "verse": 16
            },
            {
                "reference": "Psalm 23:1",
                "text": "The LORD is my shepherd; I shall not want.",
                "book": "Psalms",
                "chapter": 23,
                "verse": 1
            },
            {
                "reference": "Romans 8:28",
                "text": "And we know that all things work together for good to them that love God, to them who are the called according to his purpose.",
                "book": "Romans",
                "chapter": 8,
                "verse": 28
            }
        ]
    
    def get_current_verse(self) -> Dict:
        """Get verse based on current display mode."""
        # Check if we need to reset daily counter
        now = datetime.now()
        if now.date() > self.daily_reset_time.date():
            self.statistics['verses_today'] = 0
            self.daily_reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        self.statistics['verses_displayed'] += 1
        self.statistics['verses_today'] += 1
        
        # Track daily activity with rotation
        today_str = now.strftime('%Y-%m-%d')
        self.statistics['daily_activity'][today_str] = self.statistics['daily_activity'].get(today_str, 0) + 1
        
        # Rotate old daily activity data to prevent unbounded growth
        self._rotate_daily_activity()
        
        # Handle random translation selection
        original_translation = self.translation
        original_secondary_translation = getattr(self, 'secondary_translation', 'amp')
        
        # Initialize resolved translation variables with current values (in case of exceptions)
        resolved_translation = self.translation
        resolved_secondary_translation = getattr(self, 'secondary_translation', 'amp')
        
        # Select random translations if needed
        if self.translation == 'random':
            self.translation = self._get_random_translation()
            resolved_translation = self.translation  # Update resolved value after random selection
        
        if hasattr(self, 'secondary_translation') and self.secondary_translation == 'random':
            # Ensure secondary translation is different from primary when both are random
            import random
            secondary_options = [t for t in self.get_available_translations() if t != 'random' and t != self.translation]
            self.secondary_translation = random.choice(secondary_options) if secondary_options else 'amp'
            resolved_secondary_translation = self.secondary_translation  # Update resolved value after random selection
        
        try:
            if self.display_mode == 'date':
                verse_data = self._get_date_based_verse()
            elif self.display_mode == 'random':
                verse_data = self._get_random_verse()
            elif self.display_mode == 'devotional':
                verse_data = self._get_devotional_verse()
            elif self.display_mode == 'weather':
                verse_data = self._get_weather_data()
            elif self.display_mode == 'news':
                verse_data = self._get_news_data()
            else:  # time mode
                verse_data = self._get_time_based_verse()
            
            # Add parallel translation if enabled (for all modes except date events) - BEFORE restoring translations
            if self.parallel_mode and verse_data and not verse_data.get('is_date_event'):
                verse_data = self._add_parallel_translation(verse_data)
            
        finally:
            # Restore original translation settings
            self.translation = original_translation
            if hasattr(self, 'secondary_translation'):
                self.secondary_translation = original_secondary_translation
        
        # Ensure translation field is set if not already present
        if verse_data and not verse_data.get('translation'):
            verse_data['translation'] = self.translation.upper()
        
        # Add time format and mode information for the image generator
        if verse_data:
            verse_data['time_format'] = self.time_format
            verse_data['display_mode'] = self.display_mode
            
            # Add current_time for random mode to show actual time with verse
            if self.display_mode == 'random':
                now = datetime.now()
                hour_12 = now.hour % 12
                if hour_12 == 0:
                    hour_12 = 12
                verse_data['current_time'] = f"{hour_12:02d}:{now.minute:02d} {now.strftime('%p')}"
        
        
        # Update statistics with rotation
        self.statistics['mode_usage'][self.display_mode] += 1
        
        # Track parallel mode usage separately
        if self.parallel_mode and verse_data and verse_data.get('parallel_mode'):
            self.statistics['mode_usage']['parallel'] += 1
        
        if verse_data.get('book'):
            self.statistics['books_accessed'].add(verse_data['book'])
            # Limit books_accessed set size to prevent memory growth
            self._rotate_books_accessed()
        
        # Track primary translation using resolved value
        translation = resolved_translation
        self.statistics['translation_usage'][translation] = self.statistics['translation_usage'].get(translation, 0) + 1
        
        # Track secondary translation when in parallel mode using resolved value
        if self.parallel_mode and verse_data and verse_data.get('parallel_mode'):
            secondary_translation = resolved_secondary_translation
            self.statistics['translation_usage'][secondary_translation] = self.statistics['translation_usage'].get(secondary_translation, 0) + 1
        
        # Limit translation_usage dict size
        self._rotate_translation_usage()
        
        # Enhanced statistics tracking
        self._update_enhanced_statistics(verse_data, now)
        
        # Rotate enhanced statistics to prevent storage issues
        self._rotate_enhanced_statistics()
        
        # IMPORTANT: Restore original translation settings for UI persistence
        # This ensures that if the user selected "random", the UI dropdown stays on "random"
        # instead of changing to whatever translation was randomly selected
        self.translation = original_translation
        if hasattr(self, 'secondary_translation'):
            self.secondary_translation = original_secondary_translation
        
        return verse_data
    
    def _get_devotional_verse(self) -> Dict:
        """Get devotional content using the devotional manager."""
        if not self.devotional_manager:
            self.logger.warning("Devotional manager not available, falling back to random verse")
            return self._get_random_verse()
        
        try:
            # Get rotating devotional from the devotional manager
            devotional_data = self.devotional_manager.get_rotating_devotional()
            
            if devotional_data:
                # Convert devotional data to verse format
                return {
                    'reference': devotional_data.get('reference', devotional_data.get('scripture_reference', 'Today\'s Devotional')),
                    'text': devotional_data.get('devotional_text', devotional_data.get('text', 'No devotional content available')),
                    'book': 'Devotional',
                    'chapter': 0,
                    'verse': 0,
                    'is_devotional': True,
                    'devotional_title': self._clean_devotional_title(devotional_data.get('title', 'Today\'s Devotional')),
                    'devotional_text': devotional_data.get('devotional_text', devotional_data.get('text', '')),
                    'author': devotional_data.get('author', 'Charles Spurgeon'),
                    'source': devotional_data.get('source', 'Faith\'s Checkbook'),
                    'rotation_slot': devotional_data.get('rotation_slot', 0),
                    'rotation_minutes': devotional_data.get('rotation_minutes', 15),
                    'next_change_at': devotional_data.get('next_change_at', ''),
                    'current_time': devotional_data.get('current_time', ''),
                    'current_date': devotional_data.get('current_date', ''),
                    'current_page': devotional_data.get('current_page', 1),
                    'total_pages': devotional_data.get('total_pages', 1)
                }
            else:
                self.logger.warning("No devotional data available, falling back to random verse")
                return self._get_random_verse()
                
        except Exception as e:
            self.logger.error(f"Error getting devotional verse: {e}")
            return self._get_random_verse()
    
    def _get_time_based_verse(self) -> Dict:
        """Time-based verse logic: HH:MM = Chapter:Verse, minute 00 = book summary."""
        now = datetime.now()
        hour_24 = now.hour
        minute = now.minute
        
        # At minute 00, show a book summary
        if minute == 0:
            return self._get_random_book_summary()
        
        # For high verse numbers, show book summaries since most chapters don't have that many verses
        # Most Bible chapters have fewer than 50 verses, so minutes 50+ often won't have exact matches
        if minute >= 50:
            return self._get_random_book_summary()
        
        # Determine chapter based on time format setting
        if self.time_format == '12':
            # 12-hour format mapping:
            # 00:XX (12:XX AM) = Chapter 12
            # 01:XX (1:XX AM) = Chapter 1, 02:XX (2:XX AM) = Chapter 2, etc.
            # 12:XX (12:XX PM) = Chapter 12  
            # 13:XX (1:XX PM) = Chapter 1, 14:XX (2:XX PM) = Chapter 2, etc.
            if hour_24 == 0:
                chapter = 12  # 12:XX AM = Chapter 12
            elif hour_24 <= 12:
                chapter = hour_24  # 1:XX AM to 12:XX PM = Chapter 1-12
            else:
                chapter = hour_24 - 12  # 1:XX PM to 11:XX PM = Chapter 1-11
        else:  # 24-hour format
            # 24-hour format mapping:
            # 00:XX = Chapter 24, 01:XX = Chapter 1, etc.
            chapter = hour_24 if hour_24 > 0 else 24
        
        verse = minute
        
        verse_data = self._get_verse_from_api(chapter, verse)
        if not verse_data:
            verse_data = self._get_verse_from_local_data(chapter, verse)
        if not verse_data:
            # No exact verse found - check if we should show a summary instead
            verse_data = self._get_time_based_summary_or_fallback(chapter, verse)
        
        return verse_data
    
    def _get_time_based_summary_or_fallback(self, chapter: int, verse: int) -> Dict:
        """Get a time-based book summary when no exact verse exists, or fallback."""
        now = datetime.now()
        
        # Get books that have the requested chapter
        books_with_chapter = []
        for book in self.available_books:
            if self._book_has_chapter(book, chapter):
                books_with_chapter.append(book)
        
        if books_with_chapter:
            # Select a book based on time + daily rotation for diversity
            day_offset = now.timetuple().tm_yday  # Day of year for daily rotation
            book_index = (now.hour + now.minute + day_offset) % len(books_with_chapter)
            selected_book = books_with_chapter[book_index]
            
            # Check if ANY book has the exact verse
            has_exact_verse = any(
                self._validate_verse_number(book, chapter, verse) == verse 
                for book in books_with_chapter
            )
            
            # If no book has the exact verse, show randomized book summary instead
            if not has_exact_verse:
                return self._get_random_book_summary()
        
        # Final fallback: show randomized book summary for impossible time combinations
        # When no books have the requested chapter, show a book summary instead of a verse
        return self._get_random_book_summary()
    
    def _get_time_based_book_summary(self, book: str, chapter: int, verse: int) -> Dict:
        """Get a book summary for time-based display when exact verse doesn't exist."""
        # Get book summary
        if self.book_summaries and book in self.book_summaries:
            # New format: direct string values
            summary_text = self.book_summaries[book]
            summary = {
                'title': book,
                'summary': summary_text
            }
        else:
            # Create a basic summary if none available
            summary = {
                'title': book,
                'summary': f'{book} is a book of the Bible containing wisdom and spiritual guidance.'
            }
        
        now = datetime.now()
        # Format time with leading zeros for hours
        if self.time_format == '12':
            hour_12 = now.hour % 12
            if hour_12 == 0:
                hour_12 = 12
            time_display = f"{hour_12:02d}:{now.minute:02d} {now.strftime('%p')}"
        else:
            time_display = now.strftime('%H:%M')
        
        return {
            'reference': time_display,  # Show current time instead of book name
            'text': summary['summary'],
            'book': book,
            'chapter': 0,  # 0 indicates summary
            'verse': 0,    # 0 indicates summary
            'is_summary': True,
            'is_time_based_summary': True,
            'summary_type': 'fallback',
            'requested_time': f'{chapter:02d}:{verse:02d}',
            'current_time': time_display,
            'summary_reason': f'No Bible book contains Chapter {chapter:02d}, Verse {verse:02d}',
            'time_correlation': f'Time {time_display} → Chapter {chapter:02d}:Verse {verse:02d} → {book} Summary'
        }
    
    def _get_date_based_verse(self) -> Dict:
        """Get verse based on today's date and biblical events with enhanced hierarchical cycling."""
        now = datetime.now()
        today = now.date()
        
        # Calculate which event and verse to show based on 1-minute intervals for frequent cycling
        # This gives us 60 verse slots per hour, 1440 verse slots per day
        minutes_since_midnight = now.hour * 60 + now.minute
        verse_slot = minutes_since_midnight // 1  # 1-minute intervals
        
        # Hierarchical event collection: collect ALL events then cycle through them
        all_events = []
        event_sources = []
        
        # 1. Collect daily events (MM-DD format)
        date_key = f"{today.month:02d}-{today.day:02d}"
        if date_key in self.biblical_events_calendar.get('events', {}):
            daily_events = self.biblical_events_calendar['events'][date_key]
            for event in daily_events:
                event_copy = event.copy()
                event_copy['source_type'] = 'daily'
                all_events.append(event_copy)
            event_sources.append('daily')
        
        # 2. Collect weekly themes
        weekday_name = calendar.day_name[today.weekday()].lower()
        weekly_themes = self.biblical_events_calendar.get('weekly_themes', {})
        if weekday_name in weekly_themes:
            for event in weekly_themes[weekday_name]:
                event_copy = event.copy()
                event_copy['source_type'] = 'weekly'
                all_events.append(event_copy)
            event_sources.append('weekly')
        
        # 3. Collect monthly themes
        month_name = calendar.month_name[today.month].lower()
        monthly_themes = self.biblical_events_calendar.get('monthly_themes', {})
        if month_name in monthly_themes:
            for event in monthly_themes[month_name]:
                event_copy = event.copy()
                event_copy['source_type'] = 'monthly'
                all_events.append(event_copy)
            event_sources.append('monthly')
        
        # 4. Collect seasonal themes
        season = self._get_current_season(today)
        seasonal_themes = self.biblical_events_calendar.get('seasonal_themes', {})
        if season in seasonal_themes:
            for event in seasonal_themes[season]:
                event_copy = event.copy()
                event_copy['source_type'] = 'seasonal'
                all_events.append(event_copy)
            event_sources.append('seasonal')
        
        # 5. Collect yearly themes if available
        year_themes = self.biblical_events_calendar.get('yearly_themes', {})
        if year_themes:
            for event in year_themes:
                event_copy = event.copy()
                event_copy['source_type'] = 'yearly'
                all_events.append(event_copy)
            event_sources.append('yearly')
        
        # 6. Final fallback: Random verse if no events found
        if not all_events:
            return self._get_fallback_verse(match_type="fallback")
        
        # Determine current cycling level based on time
        selected_events = all_events
        
        # Cycle through events based on time slot
        event_index = verse_slot % len(selected_events)
        current_event = selected_events[event_index]
        
        # If we have verses, cycle through them based on time
        available_verses = current_event.get('verses', [])
        if available_verses:
            verse_in_event = verse_slot % len(available_verses)
            verse = available_verses[verse_in_event]
            
            # Parse reference to extract book, chapter, verse
            ref_parts = verse['reference'].split()
            book = ref_parts[0]
            if len(ref_parts) > 1 and ':' in ref_parts[-1]:
                chapter_verse = ref_parts[-1].split(':')
                chapter = int(chapter_verse[0]) if chapter_verse[0].isdigit() else 1
                verse_num = int(chapter_verse[1]) if len(chapter_verse) > 1 and chapter_verse[1].isdigit() else 1
            else:
                chapter = 1
                verse_num = 1
            
            # Determine the match type based on the current event's source
            match_type = current_event.get('source_type', 'mixed')
            
            return {
                'reference': verse['reference'],
                'text': verse['text'],
                'book': book,
                'chapter': chapter,
                'verse': verse_num,
                'is_date_event': True,
                'event_name': current_event.get('title', f"Biblical Event for {today.strftime('%B %d')}"),
                'event_description': current_event.get('description', 'Biblical wisdom for today'),
                'date_match': match_type,
                'source_type': current_event.get('source_type', 'mixed'),
                'cycling_info': f"Cycling through {', '.join(event_sources)} events",
                'verse_cycle_position': f"{verse_in_event + 1} of {len(available_verses)}",
                'event_cycle_position': f"{event_index + 1} of {len(selected_events)}",
                'next_change_minutes': 1 - (now.second // 60),  # 1-minute intervals
                'current_time': now.strftime('%I:%M %p'),
                'current_date': now.strftime('%B %d, %Y')
            }
        
        # Ultimate fallback to random verse with date context
        return self._get_fallback_verse(match_type="fallback")
    
    def _get_fallback_verse(self, match_type: str) -> Dict:
        """Get fallback verse for date mode with time display."""
        now = datetime.now()
        today = now.date()
        
        # Format current time for display
        if self.time_format == '12':
            hour_12 = now.hour % 12
            if hour_12 == 0:
                hour_12 = 12
            time_display = f"{hour_12:02d}:{now.minute:02d} {now.strftime('%p')}"
        else:
            time_display = now.strftime('%H:%M')
        
        fallback = random.choice(self.fallback_verses).copy()
        fallback['is_date_event'] = True
        fallback['event_name'] = f"Daily Blessing for {today.strftime('%B %d')}"
        fallback['event_description'] = "God's word for today"
        fallback['date_match'] = match_type
        fallback['verse_cycle_position'] = "1 of 1"
        fallback['event_cycle_position'] = "1 of 1"
        fallback['next_change_minutes'] = 5 - (now.minute % 5)
        fallback['reference'] = time_display  # Show current time
        fallback['current_time'] = time_display
        fallback['time_format'] = self.time_format
        
        return fallback
    
    
    def _get_verse_from_api_with_translation(self, book: str, chapter: int, verse: int, translation: str) -> Optional[Dict]:
        """Get verse from API with specific translation and validation."""
        if not self.api_url:
            return None
        
        try:
            # Validate the verse exists for this book/chapter
            validated_verse = self._validate_verse_number(book, chapter, verse)
            if not validated_verse:
                self.logger.debug(f"Verse {book} {chapter}:{verse} not valid for parallel translation")
                return None
            
            # Use the new multi-API system
            result = self._fetch_verse_from_multi_api(book, chapter, validated_verse, translation)
            if result:
                # Add adjustment info for compatibility
                result['adjusted'] = validated_verse != verse
            return result
            
        except Exception as e:
            self.logger.debug(f"API request failed for {translation} {book} {chapter}:{verse}: {e}")
            return None
    
    def _get_random_verse(self) -> Dict:
        """Get a completely random verse with time display."""
        now = datetime.now()
        if self.time_format == '12':
            hour_12 = now.hour % 12
            if hour_12 == 0:
                hour_12 = 12
            time_display = f"{hour_12:02d}:{now.minute:02d} {now.strftime('%p')}"
        else:
            time_display = now.strftime('%H:%M')
        
        fallback = random.choice(self.fallback_verses).copy()
        # Keep the original verse reference (don't overwrite it with time)
        fallback['current_time'] = time_display
        fallback['time_format'] = self.time_format
        return fallback
    
    def _get_random_book_summary(self) -> Dict:
        """Get a random book summary, using cached summary for pagination within the same minute."""
        now = datetime.now()
        current_minute = now.minute
        
        # Check if we need a new book summary (new minute or no cached summary)
        if (self.current_book_summary is None or 
            self.book_summary_minute != current_minute):
            
            # Generate new book summary
            if self.book_summaries:
                book = random.choice(list(self.book_summaries.keys()))
                # New format: direct string values
                summary_text = self.book_summaries[book]
                summary = {
                    'title': book,
                    'summary': summary_text
                }
            else:
                # Fallback if no summaries available
                book = random.choice(self.available_books)
                summary = {
                    'title': book,
                    'summary': f'{book} is a book of the Bible containing wisdom and spiritual guidance.'
                }
            
            # Cache the book summary for this minute
            self.current_book_summary = summary
            self.book_summary_minute = current_minute
            self.logger.debug(f"Generated new book summary for minute {current_minute}: {summary['title']}")
        else:
            # Use cached book summary
            summary = self.current_book_summary
            self.logger.debug(f"Using cached book summary for minute {current_minute}: {summary['title']}")
        
        # For time-based display, the reference will show current time
        if self.time_format == '12':
            hour_12 = now.hour % 12
            if hour_12 == 0:
                hour_12 = 12
            time_display = f"{hour_12:02d}:{now.minute:02d} {now.strftime('%p')}"
        else:
            time_display = now.strftime('%H:%M')
        
        return {
            'reference': time_display,  # Show current time instead of book name
            'text': summary['summary'],
            'book': summary['title'],
            'chapter': 0,
            'verse': 0,
            'is_summary': True,
            'summary_type': 'random',
            'current_time': time_display,
            'time_format': self.time_format  # Include time format for image generator
        }
    
    def _get_verse_from_api(self, chapter: int, verse: int) -> Optional[Dict]:
        """Get verse from API using systematic book selection and comprehensive validation."""
        if not self.api_url:
            return None
        
        try:
            # Get all books that have this chapter systematically
            all_candidate_books = self._get_all_books_with_valid_verse(chapter, verse)
            
            if not all_candidate_books:
                self.logger.debug(f"No books found with valid verse {chapter}:{verse}")
                return None
            
            # Prioritize books with exact verse match, then use time-based selection
            exact_match_books = [book for book in all_candidate_books if book['exact_match']]
            
            if exact_match_books:
                # Use time + day-based selection for better diversity
                now = datetime.now()
                # Add day of year to create daily rotation while maintaining time correlation
                day_offset = now.timetuple().tm_yday  # Day of year (1-365/366)
                book_index = (now.hour + now.minute + day_offset) % len(exact_match_books)
                selected_book_data = exact_match_books[book_index]
                self.logger.debug(f"Selected exact match: {selected_book_data['book']} {chapter}:{selected_book_data['verse']} (day offset: {day_offset})")
            else:
                # Fall back to any valid book with daily rotation
                now = datetime.now()
                day_offset = now.timetuple().tm_yday  # Day of year (1-365/366)
                book_index = (now.hour + now.minute + day_offset) % len(all_candidate_books)
                selected_book_data = all_candidate_books[book_index]
                self.logger.debug(f"Selected adjusted verse: {selected_book_data['book']} {chapter}:{selected_book_data['verse']} (requested {verse}, day offset: {day_offset})")
            
            book = selected_book_data['book']
            actual_verse = selected_book_data['verse']
            
            url = f"{self.api_url}/{book} {chapter}:{actual_verse}"
            # Always add translation parameter - bible-api.com default is NOT KJV
            url += f"?translation={self.translation}"
            
            try:
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()
                
                data = response.json()
                verse_text = data.get('text', '').strip()
                
                if verse_text:
                    return {
                        'reference': f"{book} {chapter:02d}:{actual_verse:02d}",
                        'text': verse_text,
                        'book': book,
                        'chapter': chapter,
                        'verse': actual_verse,
                        'original_request': f"{chapter}:{verse}",
                        'adjusted': actual_verse != verse
                    }
                else:
                    self.logger.debug(f"Empty verse returned from API for {book} {chapter}:{actual_verse}")
                    
            except requests.exceptions.RequestException as e:
                self.logger.debug(f"API request failed for {book} {chapter}:{actual_verse}: {e}")
                return None
            
            return None
            
        except Exception as e:
            self.logger.warning(f"API request failed: {e}")
            return None
    
    def _get_verse_from_local_data(self, chapter: int, verse: int) -> Optional[Dict]:
        """Get verse from local KJV data."""
        try:
            # Get books that have the required chapter
            books_with_chapter = self._get_books_with_chapter(chapter)
            
            if not books_with_chapter:
                self.logger.warning(f"No books found with chapter {chapter}")
                return None
            
            # Use daily rotation for consistent but diverse selection
            now = datetime.now()
            day_offset = now.timetuple().tm_yday  # Day of year for daily rotation
            # Sort books consistently, then rotate based on time + day
            books_with_chapter = sorted(books_with_chapter)
            rotation_offset = (now.hour + now.minute + day_offset) % len(books_with_chapter)
            books_with_chapter = books_with_chapter[rotation_offset:] + books_with_chapter[:rotation_offset]
            
            for book in books_with_chapter:
                book_data = self.kjv_bible.get(book, {})
                chapter_data = book_data.get(str(chapter), {})
                verse_text = chapter_data.get(str(verse))
                
                if verse_text:
                    return {
                        'reference': f"{book} {chapter:02d}:{verse:02d}",
                        'text': verse_text,
                        'book': book,
                        'chapter': chapter,
                        'verse': verse
                    }
            
            # If exact verse not found, try to find a verse in the chapter
            for book in books_with_chapter:
                book_data = self.kjv_bible.get(book, {})
                chapter_data = book_data.get(str(chapter), {})
                
                if chapter_data:
                    # Get the highest verse number available in this chapter
                    available_verses = [int(v) for v in chapter_data.keys() if v.isdigit()]
                    if available_verses:
                        # Use the verse number closest to what we want, but not exceeding it
                        suitable_verses = [v for v in available_verses if v <= verse]
                        if suitable_verses:
                            actual_verse = max(suitable_verses)
                        else:
                            actual_verse = min(available_verses)
                        
                        verse_text = chapter_data[str(actual_verse)]
                        
                        return {
                            'reference': f"{book} {chapter:02d}:{actual_verse:02d}",
                            'text': verse_text,
                            'book': book,
                            'chapter': chapter,
                            'verse': actual_verse
                        }
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Local data lookup failed: {e}")
            return None
    
    def _get_week_events(self, target_date: date) -> List[Dict]:
        """Get events from the same week of the year."""
        target_week = target_date.isocalendar()[1]
        week_events = []
        
        for date_key, event in self.biblical_calendar.items():
            try:
                month, day = map(int, date_key.split('-'))
                event_date = date(target_date.year, month, day)
                event_week = event_date.isocalendar()[1]
                
                if abs(event_week - target_week) <= 1:  # Same or adjacent week
                    week_events.append(event)
            except (ValueError, TypeError):
                continue
        
        return week_events
    
    def _get_month_events(self, target_month: int) -> List[Dict]:
        """Get events from the same month."""
        month_events = []
        
        for date_key, event in self.biblical_calendar.items():
            try:
                month, day = map(int, date_key.split('-'))
                if month == target_month:
                    month_events.append(event)
            except (ValueError, TypeError):
                continue
        
        return month_events
    
    def _get_season_event(self, target_date: date) -> Optional[Dict]:
        """Get event based on current season."""
        # Determine season
        month = target_date.month
        day = target_date.day
        
        if (month == 12 and day >= 21) or month in [1, 2] or (month == 3 and day < 20):
            season = "winter"
            season_key = "12-21"  # Winter solstice
        elif (month == 3 and day >= 20) or month in [4, 5] or (month == 6 and day < 21):
            season = "spring"
            season_key = "3-21"  # Spring equinox
        elif (month == 6 and day >= 21) or month in [7, 8] or (month == 9 and day < 22):
            season = "summer"
            season_key = "6-21"  # Summer solstice
        else:
            season = "autumn"
            season_key = "9-22"  # Autumn equinox
        
        return self.biblical_calendar.get(season_key)
    
    def _get_default_biblical_calendar(self):
        """Default biblical calendar events."""
        return {
            "1-1": {
                "event": "New Year - God's Covenant Renewal",
                "reference": "Lamentations 3:22-23",
                "text": "It is of the LORD'S mercies that we are not consumed, because his compassions fail not. They are new every morning: great is thy faithfulness.",
                "description": "God's mercies are renewed each morning, making New Year a time of fresh beginnings."
            },
            "12-25": {
                "event": "Christmas - Birth of Christ",
                "reference": "Luke 2:11",
                "text": "For unto you is born this day in the city of David a Saviour, which is Christ the Lord.",
                "description": "The birth of Jesus Christ, our Savior and Lord."
            },
            "6-21": {
                "event": "Summer Solstice - God's Light",
                "reference": "Psalm 84:11",
                "text": "For the LORD God is a sun and shield: the LORD will give grace and glory: no good thing will he withhold from them that walk uprightly.",
                "description": "The longest day celebrates God as our light and source of life."
            }
        }
    
    def get_statistics(self) -> Dict:
        """Get usage statistics with enhanced filtering and visualization data."""
        stats = self.statistics.copy()
        stats['books_accessed'] = list(stats['books_accessed'])
        stats['uptime'] = self.start_time.isoformat()
        
        # Clean duplicate verse history entries (one-time cleanup)
        stats['detailed_verse_history'] = self._deduplicate_verse_history(stats['detailed_verse_history'])
        
        # Add enhanced statistics
        stats['enhanced'] = {
            'book_chapter_visualization': self._get_book_chapter_visualization(),
            'timeline_data': self._get_timeline_data(),
            'filter_summaries': self._get_filter_summaries()
        }
        
        return stats
    
    def _increment_daily_cache_count(self):
        """Increment the daily cache count, resetting if it's a new day."""
        try:
            today = datetime.now().date()
            
            # Reset daily count if it's a new day
            if today != self.statistics['cache_daily_reset']:
                self.statistics['verses_cached_today'] = 0
                self.statistics['cache_daily_reset'] = today
                self.logger.info(f"Reset daily cache count for new day: {today}")
            
            # Increment today's count
            self.statistics['verses_cached_today'] += 1
            
        except Exception as e:
            self.logger.error(f"Error updating daily cache count: {e}")
    
    def get_filtered_statistics(self, filter_type='all', start_date=None, end_date=None) -> Dict:
        """Get statistics filtered by time period."""
        if filter_type == 'today':
            target_date = datetime.now().strftime('%Y-%m-%d')
            return self._get_daily_stats(target_date)
        elif filter_type == 'weekly':
            return self._get_weekly_stats()
        elif filter_type == 'monthly':
            return self._get_monthly_stats()
        elif filter_type == 'yearly':
            return self._get_yearly_stats()
        elif filter_type == 'custom' and start_date and end_date:
            return self._get_custom_range_stats(start_date, end_date)
        else:
            return self.get_statistics()
    
    def set_display_mode(self, mode: str):
        """Set display mode."""
        if mode in ['time', 'date', 'random', 'devotional', 'weather', 'news']:
            self.display_mode = mode
            self.logger.info(f"Display mode changed to: {mode}")
        else:
            raise ValueError(f"Invalid display mode: {mode}")
    
    def _add_parallel_translation(self, verse_data: Dict) -> Dict:
        """Add secondary translation for parallel mode."""
        if not verse_data or not hasattr(self, 'secondary_translation'):
            return verse_data
        
        try:
            # Handle book summaries differently
            if verse_data.get('is_summary'):
                # For book summaries, we'll show the same summary but with different translation labels
                # This allows parallel mode to work for summaries too
                verse_data['parallel_mode'] = True
                verse_data['secondary_text'] = verse_data['text']  # Same summary text for both columns
                verse_data['primary_translation'] = self.translation.upper()
                verse_data['secondary_translation'] = self.secondary_translation.upper()
                self.logger.info(f"Added parallel mode for book summary: {verse_data['book']}")
                return verse_data
            
            # Extract book, chapter, verse from primary verse
            book = verse_data['book']
            chapter = verse_data['chapter']
            verse = verse_data['verse']
            
            # Use the multi-API system to get the secondary translation
            secondary_verse = self._fetch_verse_from_multi_api(book, chapter, verse, self.secondary_translation)
            
            if secondary_verse and secondary_verse.get('text'):
                verse_data['parallel_mode'] = True
                verse_data['secondary_text'] = secondary_verse['text']
                verse_data['primary_translation'] = self.translation.upper()
                verse_data['secondary_translation'] = self.secondary_translation.upper()
                self.logger.info(f"Added parallel translation: {self.secondary_translation}")
            else:
                self.logger.warning(f"Empty secondary translation for {book} {chapter}:{verse}")
                
        except Exception as e:
            self.logger.warning(f"Failed to get parallel translation {self.secondary_translation}: {e}")
            
            # For translations marked as 'fallback', try KJV as fallback
            secondary_config = self.supported_translations.get(self.secondary_translation, {})
            if secondary_config.get('api') == 'fallback':
                try:
                    self.logger.info(f"Trying KJV fallback for {self.secondary_translation}")
                    kjv_verse = self._fetch_verse_from_multi_api(book, chapter, verse, 'kjv')
                    if kjv_verse and kjv_verse.get('text'):
                        verse_data['parallel_mode'] = True
                        verse_data['secondary_text'] = kjv_verse['text']
                        verse_data['primary_translation'] = self.translation.upper()
                        verse_data['secondary_translation'] = self.secondary_translation.upper()
                        self.logger.info(f"Using KJV text as fallback for {self.secondary_translation}")
                        return verse_data
                except Exception as kjv_error:
                    self.logger.warning(f"Failed to get KJV fallback for {self.secondary_translation}: {kjv_error}")
            
            # Always enable parallel mode with fallback text when API fails
            # This ensures parallel mode stays consistent even with API issues
            verse_data['parallel_mode'] = True
            
            if "429" in str(e) or "Too Many Requests" in str(e):
                # For rate limiting, show a temporary message
                verse_data['secondary_text'] = f"[{self.secondary_translation.upper()} - API Rate Limited - Please Wait]"
            elif "404" in str(e) or "Not Found" in str(e):
                # For complete translations like AMP, this likely means the API doesn't support it yet
                verse_data['secondary_text'] = f"[{self.secondary_translation.upper()} translation requires different API - currently using bible-api.com which only supports: KJV, WEB, ASV, BBE, Darby]"
                self.logger.info(f"404 error for {self.secondary_translation} - bible-api.com doesn't support this translation")
            else:
                # Generic network/server errors
                verse_data['secondary_text'] = f"[{self.secondary_translation.upper()} - Network Error]"
            
            verse_data['primary_translation'] = self.translation.upper()
            verse_data['secondary_translation'] = self.secondary_translation.upper()
            self.logger.info(f"Parallel mode enabled with fallback due to API issue: {verse_data['secondary_text'][:40]}...")
            
        return verse_data

    def _get_current_season(self, today):
        """Get the current season based on the date."""
        month = today.month
        day = today.day
        
        # Spring: March 20 - June 20
        if (month == 3 and day >= 20) or (month in [4, 5]) or (month == 6 and day < 21):
            return 'spring'
        # Summer: June 21 - September 21
        elif (month == 6 and day >= 21) or (month in [7, 8]) or (month == 9 and day < 22):
            return 'summer'
        # Autumn/Fall: September 22 - December 20
        elif (month == 9 and day >= 22) or (month in [10, 11]) or (month == 12 and day < 21):
            return 'autumn'
        # Winter: December 21 - March 19
        else:
            return 'winter'


    def _fetch_verse_from_multi_api(self, book: str, chapter: int, verse: int, translation: str) -> Optional[Dict]:
        """Fetch verse using hierarchical fallback system for maximum reliability."""
        if translation not in self.supported_translations:
            self.logger.warning(f"Unsupported translation: {translation}, falling back to KJV")
            translation = 'kjv'
        
        # Define optimized hierarchical fallback chains for each translation
        fallback_chains = {
            # Primary translation - highest reliability (bible-api.com)
            'kjv': [
                ('local_cache', 'kjv'),     # Primary: Local cache
                ('bible-api', 'kjv'),       # Secondary: bible-api.com (reliable)
                ('wldeh_api', 'kjv')        # Tertiary: wldeh API backup
            ],
            
            
            # Modern copyrighted translations (require scraping/special APIs)
            'amp': [
                ('local_cache', 'amp'),     # Primary: Growing local cache
                ('web_scraping', 'AMP'),    # Secondary: Direct website scraping (BibleGateway)
                ('bible_scraper', 'AMP'),   # Tertiary: YouVersion scraper
                ('scripture_api', 'AMP'),   # Quaternary: Scripture API (api.bible)
                ('biblegateway', 'AMP'),    # Quinary: BibleGateway API (with credentials)
                ('bible-api', 'kjv')        # Final: KJV fallback
            ],
            'nlt': [
                ('local_cache', 'nlt'),     # Primary: Growing local cache
                ('web_scraping', 'NLT'),    # Secondary: Direct web scraping (reliable)
                ('biblegateway', 'NLT'),    # Tertiary: BibleGateway API
                ('bible_scraper', 'NLT'),   # Quaternary: YouVersion scraper (may have 404 issues)
                ('bible-api', 'kjv')        # Final: KJV fallback
            ],
            'msg': [
                ('local_cache', 'msg'),     # Primary: Growing local cache
                ('web_scraping', 'MSG'),    # Secondary: Direct web scraping (reliable)
                ('biblegateway', 'MSG'),    # Tertiary: BibleGateway API
                ('bible_scraper', 'MSG'),   # Quaternary: YouVersion scraper (may have 404 issues)
                ('bible-api', 'kjv')        # Final: KJV fallback
            ],
            'esv': [
                ('local_cache', 'esv'),     # Primary: Growing local cache
                ('web_scraping', 'ESV'),    # Secondary: Direct web scraping (reliable)
                ('esv_api', None),          # Tertiary: Official ESV API
                ('bible_scraper', 'ESV'),   # Quaternary: YouVersion scraper (may have 404 issues)
                ('bible-api', 'kjv')        # Final: KJV fallback
            ],
            'nasb': [
                ('local_cache', 'nasb'),        # Primary: Growing local cache
                ('web_scraping', 'NASB1995'),  # Secondary: Direct web scraping (reliable)
                ('biblegateway', 'NASB1995'),   # Tertiary: BibleGateway API (NASB 1995)
                ('bible_scraper', 'NASB1995'),  # Quaternary: YouVersion scraper (may have 404 issues)
                ('bible-api', 'kjv')        # Final: KJV fallback
            ],
            'cev': [
                ('local_cache', 'cev'),     # Primary: Growing local cache
                ('web_scraping', 'CEV'),    # Secondary: Direct website scraping (BibleGateway)
                ('bible_scraper', 'CEV'),   # Tertiary: YouVersion scraper
                ('scripture_api', 'CEV'),   # Quaternary: Scripture API (api.bible)
                ('biblegateway', 'CEV'),    # Quinary: BibleGateway API (with credentials)
                ('bible-api', 'kjv')        # Final: KJV fallback
            ]
        }
        
        # Get the fallback chain for this translation
        chain = fallback_chains.get(translation, [('bible-api', 'kjv')])
        
        for api_source, source_code in chain:
            try:
                result = None
                
                if api_source == 'local_cache':
                    result = self._fetch_from_local_cache(book, chapter, verse, source_code)
                elif api_source == 'local_amp':  # Legacy support
                    result = self._fetch_from_local_amp(book, chapter, verse)
                elif api_source == 'local_kjv':  # Legacy support
                    result = self._fetch_from_local_kjv(book, chapter, verse)
                elif api_source == 'youversion':
                    result = self._fetch_from_youversion(book, chapter, verse, source_code)
                elif api_source == 'web_scraping':
                    result = self._fetch_from_web_scraping(book, chapter, verse, source_code)
                elif api_source == 'bible_scraper':
                    result = self._fetch_from_bible_scraper(book, chapter, verse, source_code)
                elif api_source == 'wldeh_api':
                    result = self._fetch_from_wldeh_api(book, chapter, verse, source_code)
                elif api_source == 'bible-api':
                    result = self._fetch_from_bible_api(book, chapter, verse, source_code)
                elif api_source == 'esv_api':
                    result = self._fetch_from_esv_api(book, chapter, verse)
                elif api_source == 'scripture_api':
                    result = self._fetch_from_scripture_api(book, chapter, verse, source_code)
                elif api_source == 'biblegateway':
                    result = self._fetch_from_biblegateway_api(book, chapter, verse, source_code)
                    
                if result and result.get('text'):
                    # Add source information for debugging
                    result['api_source'] = api_source
                    result['source_translation'] = source_code or translation
                    
                    # Add fallback notation if not the original translation
                    # Special case: treat NASB and NASB1995 as equivalent
                    is_nasb_equivalent = (
                        (translation.lower() == 'nasb' and source_code.lower() == 'nasb1995') or
                        (translation.lower() == 'nasb1995' and source_code.lower() == 'nasb')
                    )
                    
                    if source_code and source_code.lower() != translation.lower() and not is_nasb_equivalent:
                        result['text'] = f"[{translation.upper()} unavailable - showing {source_code.upper()}] {result['text']}"
                        result['translation'] = f"{translation.upper()} (fallback: {source_code.upper()})"
                    else:
                        result['translation'] = translation.upper()
                    
                    self.logger.info(f"Successfully fetched {source_code or translation} verse from {api_source}")
                    return result
                    
            except Exception as e:
                self.logger.debug(f"Failed to fetch from {api_source} for {translation}: {e}")
                continue
        
        # Final fallback to default verses
        self.logger.warning(f"All API sources failed for {translation} {book} {chapter}:{verse}")
        
        # Track translation failures for statistics
        if 'translation_failures' not in self.statistics:
            self.statistics['translation_failures'] = {}
        self.statistics['translation_failures'][translation] = self.statistics['translation_failures'].get(translation, 0) + 1
        
        return self._get_final_fallback_verse(book, chapter, verse, translation)
    
    def _fetch_from_local_amp(self, book: str, chapter: int, verse: int) -> Optional[Dict]:
        """Fetch verse from local AMP Bible file (limited sample data only)."""
        if not hasattr(self, 'amp_bible') or not self.amp_bible:
            self.logger.debug("No local AMP Bible data available")
            return None
            
        try:
            if (book in self.amp_bible and 
                str(chapter) in self.amp_bible[book] and 
                str(verse) in self.amp_bible[book][str(chapter)]):
                
                amp_text = self.amp_bible[book][str(chapter)][str(verse)]
                self.logger.info(f"Found AMP verse in limited local data: {book} {chapter}:{verse}")
                return {
                    'reference': f"{book} {chapter:02d}:{verse:02d}",
                    'text': amp_text,
                    'book': book,
                    'chapter': chapter,
                    'verse': verse,
                    'translation': 'AMP',
                    'source_note': 'Local sample data'
                }
            else:
                self.logger.debug(f"AMP verse not in local sample data: {book} {chapter}:{verse}")
                
        except Exception as e:
            self.logger.debug(f"Error accessing local AMP Bible: {e}")
        return None
    
    def _fetch_from_local_kjv(self, book: str, chapter: int, verse: int) -> Optional[Dict]:
        """Fetch verse from local KJV Bible file."""
        if not hasattr(self, 'kjv_bible') or not self.kjv_bible:
            return None
            
        try:
            if (book in self.kjv_bible and 
                str(chapter) in self.kjv_bible[book] and 
                str(verse) in self.kjv_bible[book][str(chapter)]):
                
                kjv_text = self.kjv_bible[book][str(chapter)][str(verse)]
                return {
                    'reference': f"{book} {chapter:02d}:{verse:02d}",
                    'text': kjv_text,
                    'book': book,
                    'chapter': chapter,
                    'verse': verse,
                    'translation': 'KJV'
                }
        except Exception as e:
            self.logger.debug(f"Error accessing local KJV Bible: {e}")
        return None
    
    def _fetch_from_youversion(self, book: str, chapter: int, verse: int, translation_code: str) -> Optional[Dict]:
        """Fetch verse from YouVersion using a more practical approach."""
        try:
            # YouVersion/Bible.com has anti-scraping measures and requires JavaScript
            # Instead of complex scraping, we'll use an alternative approach:
            # BibleAPI.net which supports more translations including AMP
            
            if translation_code == 'AMP':
                # Try BibleAPI.net for AMP (they have better translation support)
                return self._fetch_from_bible_api_net(book, chapter, verse, 'AMP')
            
            # For other translations, use a simplified approach
            # This is a placeholder for a more robust implementation
            self.logger.debug(f"YouVersion API integration requires more development for {translation_code}")
            return None
            
        except Exception as e:
            self.logger.debug(f"YouVersion fetch failed: {e}")
            return None
    
    def _fetch_from_bible_api_net(self, book: str, chapter: int, verse: int, translation_code: str) -> Optional[Dict]:
        """Alternative API source for additional translations like AMP."""
        try:
            # BibleAPI.net format (alternative to bible-api.com)
            # This is a conceptual implementation - the actual API might be different
            book_mapping = {
                'Genesis': 'gen', 'Exodus': 'exo', 'Leviticus': 'lev', 'Numbers': 'num',
                'Deuteronomy': 'deu', 'Joshua': 'jos', 'Judges': 'jdg', 'Ruth': 'rut',
                '1 Samuel': '1sa', '2 Samuel': '2sa', '1 Kings': '1ki', '2 Kings': '2ki',
                '1 Chronicles': '1ch', '2 Chronicles': '2ch', 'Ezra': 'ezr', 'Nehemiah': 'neh',
                'Esther': 'est', 'Job': 'job', 'Psalms': 'psa', 'Proverbs': 'pro',
                'Ecclesiastes': 'ecc', 'Song of Solomon': 'sng', 'Isaiah': 'isa',
                'Jeremiah': 'jer', 'Lamentations': 'lam', 'Ezekiel': 'eze', 'Daniel': 'dan',
                'Matthew': 'mat', 'Mark': 'mar', 'Luke': 'luk', 'John': 'joh',
                'Acts': 'act', 'Romans': 'rom', '1 Corinthians': '1co', '2 Corinthians': '2co'
            }
            
            book_code = book_mapping.get(book, book.lower()[:3])
            
            # Note: This is a placeholder URL - actual implementation would need
            # research into available free APIs that support AMP
            url = f"https://api.bibleapi.net/v2/{translation_code.lower()}/{book_code}/{chapter}/{verse}"
            
            self.logger.debug(f"BibleAPI.net integration requires API research for {translation_code}")
            return None
            
        except Exception as e:
            self.logger.debug(f"BibleAPI.net fetch failed: {e}")
            return None
    
    def _fetch_from_wldeh_api(self, book: str, chapter: int, verse: int, translation_code: str) -> Optional[Dict]:
        """Fetch verse from wldeh bible-api (free GitHub-hosted API with 200+ versions)."""
        try:
            import requests
            
            # Book name mapping for the wldeh API
            book_mapping = {
                'Genesis': 'GEN', 'Exodus': 'EXO', 'Leviticus': 'LEV', 'Numbers': 'NUM',
                'Deuteronomy': 'DEU', 'Joshua': 'JOS', 'Judges': 'JDG', 'Ruth': 'RUT',
                '1 Samuel': '1SA', '2 Samuel': '2SA', '1 Kings': '1KI', '2 Kings': '2KI',
                '1 Chronicles': '1CH', '2 Chronicles': '2CH', 'Ezra': 'EZR', 'Nehemiah': 'NEH',
                'Esther': 'EST', 'Job': 'JOB', 'Psalms': 'PSA', 'Proverbs': 'PRO',
                'Ecclesiastes': 'ECC', 'Song of Solomon': 'SNG', 'Isaiah': 'ISA',
                'Jeremiah': 'JER', 'Lamentations': 'LAM', 'Ezekiel': 'EZE', 'Daniel': 'DAN',
                'Hosea': 'HOS', 'Joel': 'JOL', 'Amos': 'AMO', 'Obadiah': 'OBA',
                'Jonah': 'JON', 'Micah': 'MIC', 'Nahum': 'NAH', 'Habakkuk': 'HAB',
                'Zephaniah': 'ZEP', 'Haggai': 'HAG', 'Zechariah': 'ZEC', 'Malachi': 'MAL',
                'Matthew': 'MAT', 'Mark': 'MRK', 'Luke': 'LUK', 'John': 'JHN',
                'Acts': 'ACT', 'Romans': 'ROM', '1 Corinthians': '1CO', '2 Corinthians': '2CO',
                'Galatians': 'GAL', 'Ephesians': 'EPH', 'Philippians': 'PHP', 'Colossians': 'COL',
                '1 Thessalonians': '1TH', '2 Thessalonians': '2TH', '1 Timothy': '1TI',
                '2 Timothy': '2TI', 'Titus': 'TIT', 'Philemon': 'PHM', 'Hebrews': 'HEB',
                'James': 'JAS', '1 Peter': '1PE', '2 Peter': '2PE', '1 John': '1JN',
                '2 John': '2JN', '3 John': '3JN', 'Jude': 'JUD', 'Revelation': 'REV'
            }
            
            book_code = book_mapping.get(book, book.upper()[:3])
            
            # Translation mapping for wldeh API (they use specific codes)
            wldeh_translation_map = {
                'web': 'engWEB2019eb',  # World English Bible
                'kjv': 'engKJV1611',     # King James Version 
                'asv': 'engASV1901',     # American Standard Version
            }
            
            api_translation = wldeh_translation_map.get(translation_code.lower(), 'engWEB2019eb')
            
            url = f"https://cdn.jsdelivr.net/gh/wldeh/bible-api/bibles/{api_translation}/books/{book_code}/chapters/{chapter}/verses/{verse}.json"
            
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            verse_text = data.get('text', '').strip()
            
            if not verse_text:
                return None
            
            return {
                'reference': f"{book} {chapter:02d}:{verse:02d}",
                'text': verse_text,
                'book': book,
                'chapter': chapter,
                'verse': verse,
                'translation': translation_code.upper(),
                'api_source': 'wldeh_github_api'
            }
            
        except Exception as e:
            self.logger.debug(f"wldeh API fetch failed: {e}")
            return None
    
    def _fetch_from_bible_scraper(self, book: str, chapter: int, verse: int, translation_code: str) -> Optional[Dict]:
        """Fetch verse using IonicaBizau/bible-scraper for YouVersion scraping."""
        self.logger.info(f"Attempting to scrape {translation_code} verse: {book} {chapter}:{verse}")
        try:
            import subprocess
            import json
            import tempfile
            import os
            
            # Check if Node.js and npm are available
            try:
                node_result = subprocess.run(['node', '--version'], capture_output=True, check=True)
                self.logger.debug(f"Node.js version: {node_result.stdout.decode().strip()}")
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.logger.warning("Node.js not available for bible-scraper")
                return None
            
            # Create a temporary directory for bible-scraper
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create a simple Node.js script to use bible-scraper
                scraper_script = f"""
const BibleScraper = require('bible-scraper');

async function getVerse() {{
    try {{
        // YouVersion translation IDs for web scraping
        const translationId = {{
            'AMP': 1588,
            'NLT': 116,
            'MSG': 97,
            'ESV': 59,
            'NASB': 100,        // NASB 1995
            'NASB1995': 100,    // NASB 1995 (alternative name)
            'NASB2020': 2692,   // NASB 2020
            'NIV': 111,         // NIV (existing)
            'CEV': 392          // Contemporary English Version
        }};
        const id = translationId['{translation_code}'] || 1588;
        
        const scraper = new BibleScraper(id);
        const reference = '{book} {chapter}:{verse}';
        const result = await scraper.verse(reference);
        
        console.log(JSON.stringify({{
            success: true,
            data: result
        }}));
    }} catch (error) {{
        console.log(JSON.stringify({{
            success: false,
            error: error.message
        }}));
    }}
}}

getVerse();
"""
                
                script_path = os.path.join(temp_dir, 'scraper.js')
                package_json = os.path.join(temp_dir, 'package.json')
                
                # Create package.json
                with open(package_json, 'w') as f:
                    json.dump({
                        "name": "bible-scraper-temp",
                        "version": "1.0.0",
                        "dependencies": {
                            "bible-scraper": "latest"
                        }
                    }, f)
                
                # Write the scraper script
                with open(script_path, 'w') as f:
                    f.write(scraper_script)
                
                # Install bible-scraper (this might take a moment on first run)
                self.logger.debug(f"Installing bible-scraper npm package for {translation_code}")
                install_result = subprocess.run(
                    ['npm', 'install'], 
                    cwd=temp_dir,
                    capture_output=True,
                    timeout=30
                )
                
                if install_result.returncode != 0:
                    self.logger.warning(f"Failed to install bible-scraper npm package: {install_result.stderr.decode()}")
                    return None
                else:
                    self.logger.debug("bible-scraper npm package installed successfully")
                
                # Run the scraper script
                result = subprocess.run(
                    ['node', script_path],
                    cwd=temp_dir,
                    capture_output=True,
                    timeout=self.timeout,
                    text=True
                )
                
                self.logger.debug(f"Scraper result code: {result.returncode}")
                if result.stdout:
                    self.logger.debug(f"Scraper stdout: {result.stdout}")
                if result.stderr:
                    self.logger.debug(f"Scraper stderr: {result.stderr}")
                
                if result.returncode == 0:
                    try:
                        output = json.loads(result.stdout.strip())
                        self.logger.debug(f"Scraper JSON output: {output}")
                        
                        if output.get('success') and output.get('data'):
                            verse_data = output['data']
                            verse_text = verse_data.get('text', '').strip()
                            
                            if verse_text:
                                self.logger.info(f"Successfully scraped {translation_code} verse: {verse_text[:100]}...")
                                # Cache the verse for any translation
                                self._cache_translation_verse(book, chapter, verse, verse_text, translation_code.lower())
                                
                                return {
                                    'reference': f"{book} {chapter:02d}:{verse:02d}",
                                    'text': verse_text,
                                    'book': book,
                                    'chapter': chapter,
                                    'verse': verse,
                                    'translation': translation_code.upper(),
                                    'api_source': 'bible_scraper_youversion'
                                }
                            else:
                                self.logger.warning(f"bible-scraper returned empty text for {translation_code}")
                        else:
                            self.logger.warning(f"bible-scraper returned unsuccessful result: {output}")
                    except json.JSONDecodeError as je:
                        self.logger.error(f"Failed to parse scraper JSON output: {je}")
                        self.logger.error(f"Raw output: {result.stdout}")
                else:
                    self.logger.warning(f"bible-scraper script failed with code {result.returncode}: {result.stderr}")
                    
        except subprocess.TimeoutExpired:
            self.logger.warning(f"bible-scraper timed out for {translation_code}")
        except Exception as e:
            self.logger.error(f"bible-scraper fetch failed for {translation_code}: {e}")
            
        return None
    
    def _get_final_fallback_verse(self, book: str, chapter: int, verse: int, translation: str) -> Optional[Dict]:
        """Get a final fallback verse when all API sources fail."""
        try:
            # Try to get a verse from our fallback collection
            if self.fallback_verses:
                import random
                fallback = random.choice(self.fallback_verses).copy()
                fallback['text'] = f"[{translation.upper()} API unavailable] {fallback['text']}"
                fallback['translation'] = f"{translation.upper()} (fallback)"
                fallback['api_source'] = 'fallback_collection'
                return fallback
        except Exception as e:
            self.logger.error(f"Final fallback failed: {e}")
        
        # Absolute final fallback
        return {
            'reference': f"{book} {chapter:02d}:{verse:02d}",
            'text': f"[{translation.upper()} unavailable] 'For I know the plans I have for you,' declares the LORD, 'plans to prosper you and not to harm you, to give you hope and a future.' - Jeremiah 29:11",
            'book': book,
            'chapter': chapter,
            'verse': verse,
            'translation': f"{translation.upper()} (fallback)",
            'api_source': 'absolute_fallback'
        }
    
    def _fetch_from_bible_api(self, book: str, chapter: int, verse: int, translation_code: str) -> Optional[Dict]:
        """Fetch verse from bible-api.com."""
        url = f"{self.api_url}/{book} {chapter}:{verse}"
        # Always add translation parameter - bible-api.com default is NOT KJV
        url += f"?translation={translation_code}"
        
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        
        data = response.json()
        verse_text = data.get('text', '').strip()
        
        if not verse_text:
            return None
        
        # Cache the successful result
        self._cache_translation_verse(book, chapter, verse, verse_text, translation_code.lower())
        
        return {
            'reference': f"{book} {chapter:02d}:{verse:02d}",
            'text': verse_text,
            'book': book,
            'chapter': chapter,
            'verse': verse,
            'translation': translation_code.upper()
        }
    
    def _fetch_from_esv_api(self, book: str, chapter: int, verse: int) -> Optional[Dict]:
        """Fetch verse from ESV API."""
        if not self.esv_api_key:
            self.logger.debug("ESV API key not configured, continuing fallback chain")
            return None
        
        url = "https://api.esv.org/v3/passage/text/"
        headers = {
            'Authorization': f'Token {self.esv_api_key}'
        }
        params = {
            'q': f'{book} {chapter}:{verse}',
            'format': 'json',
            'include-headings': False,
            'include-footnotes': False,
            'include-verse-numbers': False,
            'include-short-copyright': False,
            'include-passage-references': False
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        response.raise_for_status()
        
        data = response.json()
        passages = data.get('passages', [])
        if not passages:
            return None
        
        verse_text = passages[0].strip()
        if not verse_text:
            return None
        
        # Cache the successful ESV result
        self._cache_translation_verse(book, chapter, verse, verse_text, 'esv')
        
        return {
            'reference': f"{book} {chapter:02d}:{verse:02d}",
            'text': verse_text,
            'book': book,
            'chapter': chapter,
            'verse': verse,
            'translation': 'ESV'
        }
    
    def _fetch_from_scripture_api(self, book: str, chapter: int, verse: int, bible_id: str) -> Optional[Dict]:
        """Fetch verse from local AMP Bible or scripture.api.bible."""
        # First, try to get verse from local AMP Bible
        if hasattr(self, 'amp_bible') and self.amp_bible:
            try:
                if book in self.amp_bible and str(chapter) in self.amp_bible[book] and str(verse) in self.amp_bible[book][str(chapter)]:
                    amp_text = self.amp_bible[book][str(chapter)][str(verse)]
                    return {
                        'reference': f"{book} {chapter:02d}:{verse:02d}",
                        'text': amp_text,
                        'book': book,
                        'chapter': chapter,
                        'verse': verse,
                        'translation': 'AMP'
                    }
            except Exception as e:
                self.logger.debug(f"Error accessing local AMP Bible: {e}")
        
        # If not in local AMP Bible, try the API (though AMP may not be available)
        if not self.scripture_api_key:
            self.logger.debug("Scripture API key not configured, continuing fallback chain")
            return None
        
        # Convert book name to standard abbreviation for Scripture API
        book_mapping = {
            'Acts': 'ACT', 'Romans': 'ROM', 'Genesis': 'GEN', 'Matthew': 'MAT',
            'Mark': 'MRK', 'Luke': 'LUK', 'John': 'JHN', 'Corinthians1': '1CO',
            'Corinthians2': '2CO', 'Galatians': 'GAL', 'Ephesians': 'EPH',
            'Philippians': 'PHP', 'Colossians': 'COL', 'Thessalonians1': '1TH',
            'Thessalonians2': '2TH', 'Timothy1': '1TI', 'Timothy2': '2TI',
            'Titus': 'TIT', 'Philemon': 'PHM', 'Hebrews': 'HEB', 'James': 'JAS',
            'Peter1': '1PE', 'Peter2': '2PE', 'John1': '1JN', 'John2': '2JN',
            'John3': '3JN', 'Jude': 'JUD', 'Revelation': 'REV'
        }
        
        book_abbr = book_mapping.get(book, book.upper()[:3])
        verse_id = f"{book_abbr}.{chapter}.{verse}"
        
        url = f"https://api.scripture.api.bible/v1/bibles/{bible_id}/verses/{verse_id}"
        headers = {
            'api-key': self.scripture_api_key
        }
        params = {
            'content-type': 'text',
            'include-notes': 'false',
            'include-titles': 'false',
            'include-chapter-numbers': 'false',
            'include-verse-numbers': 'false'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        response.raise_for_status()
        
        data = response.json()
        content = data.get('data', {}).get('content', '').strip()
        
        if not content:
            return None
        
        return {
            'reference': f"{book} {chapter:02d}:{verse:02d}",
            'text': content,
            'book': book,
            'chapter': chapter,
            'verse': verse,
            'translation': 'AMP'
        }
    
    def _fetch_from_biblegateway_api(self, book: str, chapter: int, verse: int, translation_code: str) -> Optional[Dict]:
        """Fetch verse from Bible Gateway API."""
        if not self.biblegateway_username or not self.biblegateway_password:
            self.logger.debug("Bible Gateway credentials not configured, continuing fallback chain")
            return None
        
        try:
            # Get access token if we don't have one
            if not self.biblegateway_token:
                self._get_biblegateway_token()
            
            # Format reference for Bible Gateway API (e.g., "Matt 5:1" or "Acts 10:7")
            reference = f"{book} {chapter}:{verse}"
            
            # Make API request
            url = f"https://api.biblegateway.com/2/bible/osis/{reference}"
            params = {
                'access_token': self.biblegateway_token,
                'translation-list': translation_code
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract verse text from the response
            # Bible Gateway API returns XML-like content that needs parsing
            content = data.get('content', '')
            if not content:
                return None
            
            # Simple text extraction (remove XML tags)
            import re
            text = re.sub(r'<[^>]+>', '', content).strip()
            
            if not text:
                return None
            
            return {
                'reference': f"{book} {chapter:02d}:{verse:02d}",
                'text': text,
                'book': book,
                'chapter': chapter,
                'verse': verse,
                'translation': translation_code
            }
            
        except Exception as e:
            self.logger.debug(f"Bible Gateway API error for {translation_code}: {e}")
            return None
    
    def _get_biblegateway_token(self):
        """Get access token from Bible Gateway API."""
        try:
            url = "https://api.biblegateway.com/2/request_access_token"
            params = {
                'username': self.biblegateway_username,
                'password': self.biblegateway_password
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            self.biblegateway_token = data.get('access_token')
            
            if not self.biblegateway_token:
                raise Exception("No access token received from Bible Gateway")
            
            self.logger.info("Successfully obtained Bible Gateway access token")
            
        except Exception as e:
            self.logger.error(f"Failed to get Bible Gateway token: {e}")
            self.biblegateway_token = None
            raise
    
    def _fetch_from_web_scraping(self, book: str, chapter: int, verse: int, translation_code: str) -> Optional[Dict]:
        """Fetch verse by scraping Bible websites directly."""
        try:
            import requests
            try:
                from bs4 import BeautifulSoup
                has_bs4 = True
            except ImportError:
                self.logger.debug("BeautifulSoup not available, using regex-based scraping")
                has_bs4 = False
            import re
            
            # BibleGateway URL format for direct verse lookup
            verse_ref = f"{book} {chapter}:{verse}"
            url = f"https://www.biblegateway.com/passage/?search={verse_ref}&version={translation_code}"
            
            # Log the attempt
            self.logger.info(f"Attempting web scraping for {verse_ref} {translation_code}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            verse_text = None
            
            if has_bs4:
                # Use BeautifulSoup for better parsing
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find the passage content - BibleGateway uses specific classes
                passage_content = soup.find('div', class_='passage-content')
                if not passage_content:
                    # Try alternative selectors
                    passage_content = soup.find('div', class_='passage-text')
                    if not passage_content:
                        passage_content = soup.find('div', class_='passage')
                
                if passage_content:
                    verse_text = passage_content.get_text().strip()
                else:
                    self.logger.warning(f"Could not find passage content for {verse_ref} {translation_code}")
            else:
                # Use regex-based parsing when BeautifulSoup is not available
                html_content = response.text
                
                # Try to extract text from passage content div using regex
                passage_patterns = [
                    r'<div[^>]*class="passage-content"[^>]*>(.*?)</div>',
                    r'<div[^>]*class="passage-text"[^>]*>(.*?)</div>',
                    r'<div[^>]*class="passage"[^>]*>(.*?)</div>',
                    r'<span[^>]*class="text"[^>]*>(.*?)</span>'
                ]
                
                for pattern in passage_patterns:
                    match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
                    if match:
                        # Extract text and clean HTML tags
                        raw_text = match.group(1)
                        # Remove HTML tags
                        verse_text = re.sub(r'<[^>]+>', '', raw_text).strip()
                        if verse_text:
                            break
                
                if not verse_text:
                    self.logger.warning(f"Regex scraping failed for {verse_ref} {translation_code}")
            
            if not verse_text:
                self.logger.warning(f"No text found in passage content for {verse_ref} {translation_code}")
                return None
            
            # Clean up the text - remove extra content
            # Split by lines and find the actual verse line
            lines = verse_text.split('\n')
            verse_line = None
            
            for line in lines:
                line = line.strip()
                # Look for line that starts with verse number or contains substantial text
                if line and (line.startswith(str(verse)) or len(line) > 20):
                    # Remove verse number at start if present
                    cleaned_line = re.sub(r'^\d+\s*', '', line).strip()
                    if len(cleaned_line) > 10:
                        verse_line = cleaned_line
                        break
            
            if not verse_line:
                # Fallback: use first substantial line
                for line in lines:
                    line = line.strip()
                    if len(line) > 20 and not line.startswith(('Read full', 'Chapter', 'in all')):
                        verse_line = line
                        break
            
            if not verse_line:
                self.logger.warning(f"Could not extract verse text for {verse_ref} {translation_code}")
                return None
            
            # Final cleanup
            verse_text = re.sub(r'\s+', ' ', verse_line).strip()
            
            # Remove common suffixes that aren't part of the verse
            verse_text = re.split(r'\s+Read full chapter', verse_text)[0]
            verse_text = re.split(r'\s+in all English', verse_text)[0]
            
            if len(verse_text) < 10:  # Sanity check
                self.logger.warning(f"Verse text too short for {verse_ref} {translation_code}: '{verse_text}'")
                return None
            
            # Log success
            self.logger.info(f"Successfully scraped {translation_code} verse: {verse_text[:50]}...")
            
            # Cache the successful result
            self._cache_translation_verse(book, chapter, verse, verse_text, translation_code.lower())
            
            return {
                'reference': f"{book} {chapter:02d}:{verse:02d}",
                'text': verse_text,
                'book': book,
                'chapter': chapter,
                'verse': verse,
                'translation': translation_code.upper()
            }
            
        except ImportError:
            self.logger.error("BeautifulSoup not available for web scraping")
            return None
        except Exception as e:
            self.logger.error(f"Web scraping error for {translation_code} {verse_ref}: {e}")
            return None
    
    def _fetch_from_scripture_api(self, book: str, chapter: int, verse: int, translation_code: str) -> Optional[Dict]:
        """Fetch verse from Scripture API (api.bible) service."""
        if not self.scripture_api_key:
            self.logger.debug("Scripture API key not configured, continuing fallback chain")
            return None
        
        try:
            # Scripture API base URL
            base_url = "https://api.scripture.api.bible/v1"
            headers = {
                'api-key': self.scripture_api_key,
                'accept': 'application/json'
            }
            
            # First, we need to find the Bible ID for AMP translation
            # This is a simplified approach - in practice you'd cache these IDs
            bibles_url = f"{base_url}/bibles"
            response = requests.get(bibles_url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            bibles_data = response.json()
            bible_id = None
            
            # Look for AMP in available Bibles
            for bible in bibles_data.get('data', []):
                name = bible.get('name', '').lower()
                abbreviation = bible.get('abbreviation', '').lower()
                if 'amplified' in name or 'amp' in abbreviation:
                    bible_id = bible.get('id')
                    break
            
            if not bible_id:
                self.logger.debug("AMP translation not found in Scripture API")
                return None
            
            # Format the verse reference (e.g., "JHN.3.16")
            book_abbr = self._get_scripture_api_book_code(book)
            if not book_abbr:
                return None
                
            verse_id = f"{book_abbr}.{chapter}.{verse}"
            
            # Fetch the verse
            verse_url = f"{base_url}/bibles/{bible_id}/verses/{verse_id}"
            params = {
                'content-type': 'text',
                'include-notes': 'false',
                'include-titles': 'false',
                'include-chapter-numbers': 'false',
                'include-verse-numbers': 'false'
            }
            
            response = requests.get(verse_url, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            verse_data = data.get('data', {})
            verse_text = verse_data.get('content', '').strip()
            
            if not verse_text:
                return None
            
            # Clean up any HTML tags that might be present
            import re
            verse_text = re.sub(r'<[^>]+>', '', verse_text).strip()
            
            # Cache the successful result
            self._cache_translation_verse(book, chapter, verse, verse_text, translation_code.lower())
            
            return {
                'reference': f"{book} {chapter:02d}:{verse:02d}",
                'text': verse_text,
                'book': book,
                'chapter': chapter,
                'verse': verse,
                'translation': translation_code.upper()
            }
            
        except Exception as e:
            self.logger.debug(f"Scripture API error for {translation_code}: {e}")
            return None
    
    def _get_scripture_api_book_code(self, book: str) -> Optional[str]:
        """Convert book name to Scripture API book code."""
        # Mapping of common book names to Scripture API codes
        book_codes = {
            'genesis': 'GEN', 'exodus': 'EXO', 'leviticus': 'LEV', 'numbers': 'NUM', 'deuteronomy': 'DEU',
            'joshua': 'JOS', 'judges': 'JDG', 'ruth': 'RUT', '1 samuel': '1SA', '2 samuel': '2SA',
            '1 kings': '1KI', '2 kings': '2KI', '1 chronicles': '1CH', '2 chronicles': '2CH',
            'ezra': 'EZR', 'nehemiah': 'NEH', 'esther': 'EST', 'job': 'JOB', 'psalms': 'PSA',
            'proverbs': 'PRO', 'ecclesiastes': 'ECC', 'song of solomon': 'SNG', 'isaiah': 'ISA',
            'jeremiah': 'JER', 'lamentations': 'LAM', 'ezekiel': 'EZK', 'daniel': 'DAN',
            'hosea': 'HOS', 'joel': 'JOL', 'amos': 'AMO', 'obadiah': 'OBA', 'jonah': 'JON',
            'micah': 'MIC', 'nahum': 'NAM', 'habakkuk': 'HAB', 'zephaniah': 'ZEP',
            'haggai': 'HAG', 'zechariah': 'ZEC', 'malachi': 'MAL',
            'matthew': 'MAT', 'mark': 'MRK', 'luke': 'LUK', 'john': 'JHN', 'acts': 'ACT',
            'romans': 'ROM', '1 corinthians': '1CO', '2 corinthians': '2CO', 'galatians': 'GAL',
            'ephesians': 'EPH', 'philippians': 'PHP', 'colossians': 'COL', '1 thessalonians': '1TH',
            '2 thessalonians': '2TH', '1 timothy': '1TI', '2 timothy': '2TI', 'titus': 'TIT',
            'philemon': 'PHM', 'hebrews': 'HEB', 'james': 'JAS', '1 peter': '1PE', '2 peter': '2PE',
            '1 john': '1JN', '2 john': '2JN', '3 john': '3JN', 'jude': 'JUD', 'revelation': 'REV'
        }
        return book_codes.get(book.lower())
    
    def _fetch_from_fallback(self, book: str, chapter: int, verse: int, translation: str) -> Optional[Dict]:
        """Fallback method for unsupported translations."""
        self.logger.info(f"Using fallback for {translation.upper()} - returning KJV with note")
        
        # Try to get KJV version as fallback
        try:
            fallback_verse = self._fetch_from_bible_api(book, chapter, verse, 'kjv')
            if fallback_verse:
                fallback_verse['text'] = f"[{translation.upper()} not yet available - showing KJV] " + fallback_verse['text']
                fallback_verse['translation'] = f"{translation.upper()} (fallback)"
                return fallback_verse
        except Exception as e:
            self.logger.warning(f"Fallback to KJV also failed for {book} {chapter}:{verse}: {e}")
        
        # Return a default verse if all else fails
        return {
            'reference': f"{book} {chapter:02d}:{verse:02d}",
            'text': f"[{translation.upper()} not available] Unable to retrieve verse.",
            'book': book,
            'chapter': chapter,
            'verse': verse,
            'translation': f"{translation.upper()} (unavailable)"
        }
    
    def get_configured_translation(self) -> str:
        """Get the user's configured primary translation (may be 'random')."""
        return getattr(self, '_configured_translation', self.translation)
    
    def get_configured_secondary_translation(self) -> str:
        """Get the user's configured secondary translation (may be 'random')."""
        return getattr(self, '_configured_secondary_translation', self.secondary_translation)
    
    def set_configured_translation(self, translation: str):
        """Set both the configured and working primary translation."""
        self._configured_translation = translation
        self.translation = translation
    
    def set_configured_secondary_translation(self, translation: str):
        """Set both the configured and working secondary translation."""
        self._configured_secondary_translation = translation
        self.secondary_translation = translation
    
    def get_available_translations(self) -> List[str]:
        """Get list of available translations."""
        translations = list(self.supported_translations.keys())
        translations.append('random')  # Add random as an available option
        return translations
    
    def get_translation_display_names(self) -> Dict[str, str]:
        """Get translation codes mapped to display names."""
        return {
            'kjv': 'King James Version (KJV)',
            'esv': 'English Standard Version (ESV)',
            'amp': 'Amplified Bible (AMP)',
            'nlt': 'New Living Translation (NLT)',
            'msg': 'The Message (MSG)',
            'nasb': 'New American Standard Bible 1995 (NASB)',
            'cev': 'Contemporary English Version (CEV)',
            'random': 'Random (Changes Each Interval)'
        }
    
    def _get_random_translation(self) -> str:
        """Get a truly random translation from available translations."""
        import random
        available_translations = [t for t in self.get_available_translations() if t != 'random']
        selected = random.choice(available_translations) if available_translations else 'kjv'
        self.logger.debug(f"Selected truly random translation: {selected}")
        return selected
    
    def _rotate_daily_activity(self):
        """Rotate daily activity data to keep only recent days."""
        if len(self.statistics['daily_activity']) <= self.MAX_DAILY_ACTIVITY_DAYS:
            return
        
        # Sort dates and keep only the most recent ones
        sorted_dates = sorted(self.statistics['daily_activity'].keys())
        excess_count = len(sorted_dates) - self.MAX_DAILY_ACTIVITY_DAYS
        
        for old_date in sorted_dates[:excess_count]:
            del self.statistics['daily_activity'][old_date]
        
        self.logger.debug(f"Rotated daily activity: removed {excess_count} old entries")
    
    def _rotate_books_accessed(self):
        """Limit books_accessed set size to prevent memory growth."""
        if len(self.statistics['books_accessed']) > self.MAX_BOOKS_ACCESSED:
            # Convert to list, sort, and keep only recent ones
            # Since it's a set, we'll just trim to the limit
            books_list = list(self.statistics['books_accessed'])
            # Keep random subset to maintain variety
            import random
            random.shuffle(books_list)
            self.statistics['books_accessed'] = set(books_list[:self.MAX_BOOKS_ACCESSED])
            self.logger.debug(f"Rotated books accessed: trimmed to {self.MAX_BOOKS_ACCESSED} entries")
    
    def _rotate_translation_usage(self):
        """Limit translation_usage dict size to prevent memory growth."""
        if len(self.statistics['translation_usage']) > self.MAX_TRANSLATION_USAGE:
            # Sort by usage count and keep the most used ones
            sorted_translations = sorted(
                self.statistics['translation_usage'].items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            # Keep only the top translations
            self.statistics['translation_usage'] = dict(sorted_translations[:self.MAX_TRANSLATION_USAGE])
            removed_count = len(sorted_translations) - self.MAX_TRANSLATION_USAGE
            self.logger.debug(f"Rotated translation usage: removed {removed_count} entries")
    
    def clean_random_from_statistics(self):
        """Remove 'random' entries from translation usage statistics."""
        if 'random' in self.statistics['translation_usage']:
            random_count = self.statistics['translation_usage'].pop('random')
            self.logger.info(f"Cleaned up random translation statistics: removed {random_count} entries")
            return random_count
        return 0

    def _fetch_from_local_cache(self, book: str, chapter: int, verse: int, translation: str) -> Optional[Dict]:
        """Fetch verse from local translation cache."""
        if not hasattr(self, 'translation_caches') or translation not in self.translation_caches:
            self.logger.debug(f"No local cache available for {translation}")
            return None
            
        try:
            cache = self.translation_caches[translation]
            if (book in cache and 
                str(chapter) in cache[book] and 
                str(verse) in cache[book][str(chapter)]):
                
                verse_text = cache[book][str(chapter)][str(verse)]
                if verse_text and verse_text.strip():
                    self.logger.debug(f"Found {translation.upper()} verse in local cache: {book} {chapter}:{verse}")
                    return {
                        'reference': f"{book} {chapter:02d}:{verse:02d}",
                        'text': verse_text.strip(),
                        'book': book,
                        'chapter': chapter,
                        'verse': verse,
                        'translation': translation.upper(),
                        'source_note': 'Local cache'
                    }
            else:
                self.logger.debug(f"{translation.upper()} verse not in local cache: {book} {chapter}:{verse}")
                
        except Exception as e:
            self.logger.debug(f"Error accessing {translation} local cache: {e}")
        return None

    def _cache_translation_verse(self, book: str, chapter: int, verse: int, text: str, translation: str) -> bool:
        """Cache a verse for any translation to build complete local Bible."""
        if not self.translation_cache_enabled or not text or not text.strip():
            return False
        
        # Normalize translation key - handle NASB special case
        normalized_translation = translation.lower()
        if normalized_translation == 'nasb1995':
            normalized_translation = 'nasb'  # Map nasb1995 to nasb for consistency
        
        if not hasattr(self, 'translation_caches'):
            self.translation_caches = {}
        
        if normalized_translation not in self.translation_caches:
            self.translation_caches[normalized_translation] = {}
        
        try:
            # Ensure the structure exists
            cache = self.translation_caches[normalized_translation]
            if book not in cache:
                cache[book] = {}
            if str(chapter) not in cache[book]:
                cache[book][str(chapter)] = {}
            
            # Only cache if we don't already have this verse
            if str(verse) not in cache[book][str(chapter)]:
                cache[book][str(chapter)][str(verse)] = text.strip()
                
                # Track daily cache additions
                self._increment_daily_cache_count()
                
                # Save to file immediately (to persist across restarts)
                self._save_translation_cache(normalized_translation)
                
                # Update completion percentage
                old_completion = self.translation_completion.get(normalized_translation, 0.0)
                self.translation_completion = self._calculate_all_translation_completion()
                new_completion = self.translation_completion.get(normalized_translation, 0.0)
                
                if new_completion > old_completion:
                    self.logger.info(f"{translation.upper()} Bible cache updated: {book} {chapter}:{verse} - "
                                   f"completion now {new_completion:.1f}%")
                
                return True
        except Exception as e:
            self.logger.error(f"Failed to cache {translation} verse {book} {chapter}:{verse}: {e}")
        
        return False
    
    def _save_translation_cache(self, translation: str):
        """Save a specific translation cache to file."""
        try:
            # Handle special case for NASB which uses nasb1995 file
            file_name = translation
            if translation == 'nasb':
                file_name = 'nasb1995'
            
            cache_path = Path(f'data/translations/bible_{file_name}.json')
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(cache_path, 'w') as f:
                json.dump(self.translation_caches[translation], f, indent=2)
            
        except Exception as e:
            self.logger.error(f"Failed to save {translation} cache: {e}")
    
    def _calculate_all_translation_completion(self) -> Dict[str, float]:
        """Calculate completion percentage for all translations."""
        if not self.bible_structure or not hasattr(self, 'translation_caches'):
            return {}
        
        completion = {}
        total_verses = self._get_total_bible_verses()
        
        for translation in self.translation_caches:
            cached_verses = 0
            cache = self.translation_caches[translation]
            
            # Count cached verses for this translation
            for book in self.available_books:
                if book in cache:
                    for chapter_str in cache[book]:
                        chapter_data = cache[book][chapter_str]
                        for verse_str, verse_text in chapter_data.items():
                            if verse_text and verse_text.strip():
                                cached_verses += 1
            
            completion[translation] = (cached_verses / total_verses * 100.0) if total_verses > 0 else 0.0
        
        return completion
    
    def _get_total_bible_verses(self) -> int:
        """Get total number of verses in the complete Bible."""
        if not self.bible_structure:
            return 31100  # Approximate Bible verse count
        
        total = 0
        for book in self.bible_structure:
            if book in self.available_books:
                for chapter_str, verse_count in self.bible_structure[book].items():
                    total += verse_count
        return total
    
    def _format_completion_summary(self) -> str:
        """Format a summary of translation completion percentages."""
        if not hasattr(self, 'translation_completion'):
            return "0 translations cached"
        
        completed = [f"{trans.upper()}: {pct:.1f}%" 
                    for trans, pct in self.translation_completion.items() 
                    if pct > 0]
        
        if not completed:
            return "No translations cached yet"
        
        return f"{len(completed)} translations cached - " + ", ".join(completed[:3]) + \
               (f" and {len(completed)-3} more" if len(completed) > 3 else "")

    def _calculate_amp_completion(self) -> float:
        """Calculate what percentage of the Bible we have in AMP translation."""
        if not self.bible_structure or not self.amp_bible:
            return 0.0
        
        total_verses = 0
        cached_verses = 0
        
        # Count total verses and cached verses
        for book in self.bible_structure:
            if book in self.available_books:  # Only count books we recognize
                for chapter_str, verse_count in self.bible_structure[book].items():
                    chapter = int(chapter_str)
                    total_verses += verse_count
                    
                    # Count how many verses we have cached for this chapter
                    if (book in self.amp_bible and 
                        str(chapter) in self.amp_bible[book]):
                        chapter_data = self.amp_bible[book][str(chapter)]
                        # Count actual verse entries (not just keys)
                        for verse_num in range(1, verse_count + 1):
                            if str(verse_num) in chapter_data and chapter_data[str(verse_num)].strip():
                                cached_verses += 1
        
        if total_verses == 0:
            return 0.0
        
        return (cached_verses / total_verses) * 100.0
    
    def _cache_amp_verse(self, book: str, chapter: int, verse: int, text: str) -> bool:
        """Cache a newly scraped AMP verse to build the complete Bible."""
        if not self.amp_cache_enabled or not text or not text.strip():
            return False
        
        try:
            # Ensure the structure exists
            if book not in self.amp_bible:
                self.amp_bible[book] = {}
            if str(chapter) not in self.amp_bible[book]:
                self.amp_bible[book][str(chapter)] = {}
            
            # Only cache if we don't already have this verse
            if str(verse) not in self.amp_bible[book][str(chapter)]:
                self.amp_bible[book][str(chapter)][str(verse)] = text.strip()
                
                # Save to file immediately (to persist across restarts)
                self._save_amp_bible()
                
                # Update completion percentage
                old_percentage = self.amp_completion_percentage
                self.amp_completion_percentage = self._calculate_amp_completion()
                
                if self.amp_completion_percentage > old_percentage:
                    self.logger.info(f"AMP Bible cache updated: {book} {chapter}:{verse} - "
                                   f"completion now {self.amp_completion_percentage:.1f}%")
                
                return True
        except Exception as e:
            self.logger.error(f"Failed to cache AMP verse {book} {chapter}:{verse}: {e}")
        
        return False
    
    def _save_amp_bible(self):
        """Save the AMP Bible cache to file."""
        try:
            amp_path = Path('data/translations/bible_amp.json')
            amp_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(amp_path, 'w') as f:
                json.dump(self.amp_bible, f, indent=2)
            
        except Exception as e:
            self.logger.error(f"Failed to save AMP Bible cache: {e}")
    
    def get_amp_completion_stats(self) -> Dict:
        """Get detailed AMP completion statistics."""
        if not self.bible_structure:
            return {"completion_percentage": 0.0, "total_verses": 0, "cached_verses": 0}
        
        total_verses = 0
        cached_verses = 0
        book_stats = {}
        
        for book in self.available_books:
            if book in self.bible_structure:
                book_total = 0
                book_cached = 0
                
                for chapter_str, verse_count in self.bible_structure[book].items():
                    chapter = int(chapter_str)
                    book_total += verse_count
                    
                    if (book in self.amp_bible and 
                        str(chapter) in self.amp_bible[book]):
                        chapter_data = self.amp_bible[book][str(chapter)]
                        for verse_num in range(1, verse_count + 1):
                            if str(verse_num) in chapter_data and chapter_data[str(verse_num)].strip():
                                book_cached += 1
                
                book_stats[book] = {
                    "total_verses": book_total,
                    "cached_verses": book_cached,
                    "completion_percentage": (book_cached / book_total * 100.0) if book_total > 0 else 0.0
                }
                
                total_verses += book_total
                cached_verses += book_cached
        
        return {
            "completion_percentage": self.amp_completion_percentage,
            "total_verses": total_verses,
            "cached_verses": cached_verses,
            "book_stats": book_stats
        }
    
    # === Enhanced Statistics Methods ===
    
    def _update_enhanced_statistics(self, verse_data: Dict, timestamp: datetime):
        """Update detailed statistics tracking."""
        try:
            if not verse_data or verse_data.get('is_date_event') or verse_data.get('is_summary'):
                return  # Skip date events and book summaries for detailed tracking
            
            # Only record one verse per minute to match display behavior
            current_minute = timestamp.strftime('%Y-%m-%d %H:%M')
            if self.last_recorded_minute == current_minute:
                return  # Already recorded a verse for this minute
            
            self.last_recorded_minute = current_minute
            
            date_str = timestamp.strftime('%Y-%m-%d')
            month_str = timestamp.strftime('%Y-%m')
            year_str = timestamp.strftime('%Y')
            
            # Update detailed verse history (keep last 1000 entries)
            history_entry = {
                'timestamp': timestamp.isoformat(),
                'date': date_str,
                'book': verse_data.get('book'),
                'chapter': verse_data.get('chapter'),
                'verse': verse_data.get('verse'),
                'translation': self.translation,
                'mode': self.display_mode,
                'reference': verse_data.get('reference')
            }
            
            self.statistics['detailed_verse_history'].append(history_entry)
            # Limit history size to prevent memory growth
            if len(self.statistics['detailed_verse_history']) > self.MAX_DETAILED_HISTORY:
                self.statistics['detailed_verse_history'] = self.statistics['detailed_verse_history'][-self.MAX_DETAILED_HISTORY:]
            
            # Update book/chapter breakdown
            book = verse_data.get('book')
            chapter = verse_data.get('chapter')
            if book and chapter:
                if book not in self.statistics['book_chapter_breakdown']:
                    self.statistics['book_chapter_breakdown'][book] = {'chapters': {}, 'total': 0}
                
                if chapter not in self.statistics['book_chapter_breakdown'][book]['chapters']:
                    self.statistics['book_chapter_breakdown'][book]['chapters'][chapter] = 0
                
                self.statistics['book_chapter_breakdown'][book]['chapters'][chapter] += 1
                self.statistics['book_chapter_breakdown'][book]['total'] += 1
            
            # Update monthly and yearly stats
            self.statistics['monthly_stats'][month_str] = self.statistics['monthly_stats'].get(month_str, 0) + 1
            self.statistics['yearly_stats'][year_str] = self.statistics['yearly_stats'].get(year_str, 0) + 1
            
        except Exception as e:
            self.logger.warning(f"Enhanced statistics update failed: {e}")
    
    def _get_book_chapter_visualization(self) -> Dict:
        """Get data for book/chapter visualization graphs."""
        try:
            breakdown = self.statistics['book_chapter_breakdown']
            
            # Prepare data for different chart types
            book_totals = []
            chapter_details = []
            
            for book, data in breakdown.items():
                book_totals.append({
                    'book': book,
                    'total_verses': data['total'],
                    'chapters_accessed': len(data['chapters'])
                })
                
                for chapter, count in data['chapters'].items():
                    chapter_details.append({
                        'book': book,
                        'chapter': chapter,
                        'verse_count': count,
                        'book_chapter': f"{book} {chapter}"
                    })
            
            # Sort by verse count
            book_totals.sort(key=lambda x: x['total_verses'], reverse=True)
            chapter_details.sort(key=lambda x: x['verse_count'], reverse=True)
            
            return {
                'book_totals': book_totals[:20],  # Top 20 books
                'chapter_details': chapter_details[:30],  # Top 30 chapters
                'total_books': len(book_totals),
                'total_chapters': len(chapter_details)
            }
        except Exception as e:
            self.logger.warning(f"Book/chapter visualization failed: {e}")
            return {'book_totals': [], 'chapter_details': [], 'total_books': 0, 'total_chapters': 0}
    
    def _get_timeline_data(self) -> Dict:
        """Get timeline data for graphs."""
        try:
            daily_data = []
            monthly_data = []
            yearly_data = []
            
            # Daily data (last 30 days)
            for date_str, count in sorted(self.statistics['daily_activity'].items())[-30:]:
                daily_data.append({'date': date_str, 'verses': count})
            
            # Monthly data
            for month_str, count in sorted(self.statistics['monthly_stats'].items()):
                monthly_data.append({'month': month_str, 'verses': count})
            
            # Yearly data
            for year_str, count in sorted(self.statistics['yearly_stats'].items()):
                yearly_data.append({'year': year_str, 'verses': count})
            
            return {
                'daily': daily_data,
                'monthly': monthly_data,
                'yearly': yearly_data
            }
        except Exception as e:
            self.logger.warning(f"Timeline data generation failed: {e}")
            return {'daily': [], 'monthly': [], 'yearly': []}
    
    def _get_filter_summaries(self) -> Dict:
        """Get summary statistics for different time filters."""
        try:
            now = datetime.now()
            today = now.strftime('%Y-%m-%d')
            this_month = now.strftime('%Y-%m')
            this_year = now.strftime('%Y')
            
            # Calculate week start (Monday)
            week_start = now - timedelta(days=now.weekday())
            week_dates = [(week_start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
            
            return {
                'today': {
                    'verses': self.statistics['daily_activity'].get(today, 0),
                    'date': today
                },
                'this_week': {
                    'verses': sum(self.statistics['daily_activity'].get(date, 0) for date in week_dates),
                    'start_date': week_dates[0],
                    'end_date': week_dates[-1]
                },
                'this_month': {
                    'verses': self.statistics['monthly_stats'].get(this_month, 0),
                    'month': this_month
                },
                'this_year': {
                    'verses': self.statistics['yearly_stats'].get(this_year, 0),
                    'year': this_year
                }
            }
        except Exception as e:
            self.logger.warning(f"Filter summaries failed: {e}")
            return {'today': {'verses': 0}, 'this_week': {'verses': 0}, 'this_month': {'verses': 0}, 'this_year': {'verses': 0}}
    
    def _get_daily_stats(self, date_str: str) -> Dict:
        """Get statistics for a specific day."""
        try:
            verses_on_date = [entry for entry in self.statistics['detailed_verse_history'] if entry['date'] == date_str]
            
            books_accessed = set(entry['book'] for entry in verses_on_date if entry['book'])
            translations_used = {}
            modes_used = {}
            
            for entry in verses_on_date:
                trans = entry.get('translation', 'unknown')
                mode = entry.get('mode', 'unknown')
                translations_used[trans] = translations_used.get(trans, 0) + 1
                modes_used[mode] = modes_used.get(mode, 0) + 1
            
            return {
                'date': date_str,
                'total_verses': len(verses_on_date),
                'books_accessed': list(books_accessed),
                'translations_used': translations_used,
                'modes_used': modes_used,
                'verses_by_hour': self._get_hourly_breakdown(verses_on_date)
            }
        except Exception as e:
            self.logger.warning(f"Daily stats failed: {e}")
            return {'date': date_str, 'total_verses': 0, 'books_accessed': [], 'translations_used': {}, 'modes_used': {}}
    
    def _get_weekly_stats(self) -> Dict:
        """Get statistics for the current week."""
        try:
            now = datetime.now()
            week_start = now - timedelta(days=now.weekday())
            week_dates = [(week_start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
            
            week_verses = [entry for entry in self.statistics['detailed_verse_history'] 
                          if entry['date'] in week_dates]
            
            daily_breakdown = {}
            for date in week_dates:
                daily_breakdown[date] = len([v for v in week_verses if v['date'] == date])
            
            return {
                'week_start': week_dates[0],
                'week_end': week_dates[-1],
                'total_verses': len(week_verses),
                'daily_breakdown': daily_breakdown,
                'most_active_day': max(daily_breakdown.items(), key=lambda x: x[1]) if daily_breakdown else ('', 0)
            }
        except Exception as e:
            self.logger.warning(f"Weekly stats failed: {e}")
            return {'total_verses': 0, 'daily_breakdown': {}}
    
    def _get_monthly_stats(self) -> Dict:
        """Get statistics for the current month."""
        try:
            this_month = datetime.now().strftime('%Y-%m')
            month_verses = [entry for entry in self.statistics['detailed_verse_history'] 
                           if entry['timestamp'].startswith(this_month)]
            
            return {
                'month': this_month,
                'total_verses': len(month_verses),
                'books_this_month': len(set(entry['book'] for entry in month_verses if entry['book'])),
                'avg_verses_per_day': len(month_verses) / datetime.now().day if month_verses else 0
            }
        except Exception as e:
            self.logger.warning(f"Monthly stats failed: {e}")
            return {'month': '', 'total_verses': 0}
    
    def _get_yearly_stats(self) -> Dict:
        """Get statistics for the current year."""
        try:
            this_year = datetime.now().strftime('%Y')
            year_verses = [entry for entry in self.statistics['detailed_verse_history'] 
                          if entry['timestamp'].startswith(this_year)]
            
            return {
                'year': this_year,
                'total_verses': len(year_verses),
                'unique_books': len(set(entry['book'] for entry in year_verses if entry['book'])),
                'monthly_breakdown': {month: self.statistics['monthly_stats'].get(f"{this_year}-{month:02d}", 0) 
                                    for month in range(1, 13)}
            }
        except Exception as e:
            self.logger.warning(f"Yearly stats failed: {e}")
            return {'year': '', 'total_verses': 0}
    
    def _get_custom_range_stats(self, start_date: str, end_date: str) -> Dict:
        """Get statistics for a custom date range."""
        try:
            range_verses = [entry for entry in self.statistics['detailed_verse_history'] 
                           if start_date <= entry['date'] <= end_date]
            
            return {
                'start_date': start_date,
                'end_date': end_date,
                'total_verses': len(range_verses),
                'date_range_days': (datetime.strptime(end_date, '%Y-%m-%d') - 
                                   datetime.strptime(start_date, '%Y-%m-%d')).days + 1,
                'avg_verses_per_day': len(range_verses) / max(1, (datetime.strptime(end_date, '%Y-%m-%d') - 
                                                                datetime.strptime(start_date, '%Y-%m-%d')).days + 1)
            }
        except Exception as e:
            self.logger.warning(f"Custom range stats failed: {e}")
            return {'start_date': start_date, 'end_date': end_date, 'total_verses': 0}
    
    def _get_hourly_breakdown(self, verse_entries: List[Dict]) -> Dict:
        """Get hourly breakdown of verses for a given day."""
        try:
            hourly_counts = {}
            for entry in verse_entries:
                timestamp = datetime.fromisoformat(entry['timestamp'])
                hour = timestamp.hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            
            return hourly_counts
        except Exception as e:
            self.logger.warning(f"Hourly breakdown failed: {e}")
            return {}
    
    def _rotate_enhanced_statistics(self):
        """Rotate enhanced statistics to prevent unbounded growth."""
        try:
            # Rotate book/chapter breakdown - keep only most accessed books
            if len(self.statistics['book_chapter_breakdown']) > self.MAX_BOOK_BREAKDOWN_BOOKS:
                # Sort books by total verse count and keep top books
                sorted_books = sorted(
                    self.statistics['book_chapter_breakdown'].items(),
                    key=lambda x: x[1]['total'],
                    reverse=True
                )
                # Keep only top books
                self.statistics['book_chapter_breakdown'] = dict(sorted_books[:self.MAX_BOOK_BREAKDOWN_BOOKS])
                self.logger.debug(f"Rotated book breakdown: kept top {self.MAX_BOOK_BREAKDOWN_BOOKS} books")
            
            # Rotate monthly stats - keep only recent months
            if len(self.statistics['monthly_stats']) > self.MAX_MONTHLY_STATS:
                sorted_months = sorted(self.statistics['monthly_stats'].items())
                self.statistics['monthly_stats'] = dict(sorted_months[-self.MAX_MONTHLY_STATS:])
                self.logger.debug(f"Rotated monthly stats: kept last {self.MAX_MONTHLY_STATS} months")
            
            # Rotate yearly stats - keep only recent years
            if len(self.statistics['yearly_stats']) > self.MAX_YEARLY_STATS:
                sorted_years = sorted(self.statistics['yearly_stats'].items())
                self.statistics['yearly_stats'] = dict(sorted_years[-self.MAX_YEARLY_STATS:])
                self.logger.debug(f"Rotated yearly stats: kept last {self.MAX_YEARLY_STATS} years")
                
        except Exception as e:
            self.logger.warning(f"Enhanced statistics rotation failed: {e}")
    
    def _get_weather_data(self) -> Dict:
        """Get weather forecast data instead of verse data."""
        try:
            from weather_service import weather_service
            
            # Check if weather data should be refreshed (hourly check)
            force_refresh = weather_service.should_refresh_weather_data()
            if force_refresh:
                self.logger.info("Weather data refresh triggered - approaching expiration")
            
            # Get complete weather data with potential force refresh
            weather_data = weather_service.get_complete_weather_data(force_refresh=force_refresh)
            
            if not weather_data:
                # Return fallback weather data
                return {
                    'text': 'Weather data unavailable',
                    'reference': 'Weather Service',
                    'book': 'Weather',
                    'chapter': 0,
                    'verse': 0,
                    'translation': 'WEATHER',
                    'is_weather_mode': True,
                    'weather_error': True,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Format weather data to look like verse data for compatibility
            current_location = weather_data.get('current_location', {})
            location_info = current_location.get('location_info', {}) if current_location else {}
            current_weather = current_location.get('weather', {}) if current_location else {}
            
            # Create a summary text for the "verse" field
            summary_parts = []
            
            # Current location summary
            if location_info and current_weather:
                city = location_info.get('city', 'Unknown')
                country = location_info.get('country', '')
                current = current_weather.get('current', {})
                temp = current.get('temperature', 0)
                temp_unit = current.get('temperature_unit', '°F')
                desc = current.get('description', 'Unknown')
                summary_parts.append(f"{city}, {country}: {temp:.0f}{temp_unit}, {desc}")
            
            # Second location summary
            second_location = weather_data.get('second_location', {})
            if second_location:
                second_weather = second_location.get('weather', {})
                second_info = second_location.get('location_info', {})
                if second_weather:
                    second_current = second_weather.get('current', {})
                    temp = second_current.get('temperature', 0)
                    temp_unit = second_current.get('temperature_unit', '°F')
                    desc = second_current.get('description', 'Unknown')
                    location_name = second_info.get('name', 'Second Location')
                    summary_parts.append(f"{location_name}: {temp:.0f}{temp_unit}, {desc}")
            
            # Moon phase summary
            moon_data = weather_data.get('moon_phases', {})
            if moon_data:
                illumination = moon_data.get('current_illumination', 50)
                summary_parts.append(f"Moon: {illumination}% illuminated")
            
            summary_text = " | ".join(summary_parts) if summary_parts else "Weather forecast available"
            
            # Update mode usage statistics
            self.statistics['mode_usage']['weather'] = self.statistics['mode_usage'].get('weather', 0) + 1
            
            weather_verse_data = {
                'text': summary_text,
                'reference': 'Weather Forecast',
                'book': 'Weather',
                'chapter': 0,
                'verse': 0,
                'translation': 'WEATHER',
                'is_weather_mode': True,
                'weather_data': weather_data,
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info("Weather data retrieved successfully")
            return weather_verse_data
            
        except Exception as e:
            self.logger.error(f"Failed to get weather data: {e}")
            return {
                'text': f'Weather service error: {str(e)}',
                'reference': 'Weather Service Error',
                'book': 'Weather',
                'chapter': 0,
                'verse': 0,
                'translation': 'ERROR',
                'is_weather_mode': True,
                'weather_error': True,
                'timestamp': datetime.now().isoformat()
            }
    
    def _get_news_data(self) -> Dict:
        """Get Israel news data instead of verse data."""
        try:
            try:
                from news_service import news_service
            except ImportError:
                # Fallback if import fails
                return self._get_fallback_news_data()
            
            # Get current article to display
            article = news_service.get_current_article()
            
            if not article:
                # Return fallback news data
                return {
                    'text': 'Israel news unavailable',
                    'reference': 'News Service',
                    'book': 'News',
                    'chapter': 0,
                    'verse': 0,
                    'translation': 'NEWS',
                    'is_news_mode': True,
                    'news_error': True,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Format news data to look like verse data for compatibility
            title = article.get('title', 'No title')
            description = article.get('description', '')
            source = article.get('source', 'Israel News')
            published_str = article.get('published_str', '')
            age_hours = article.get('age_hours', 0)
            
            # Create summary text for the "verse" field
            summary_parts = [title]
            if published_str:
                summary_parts.append(f"Published: {published_str}")
            if age_hours < 24:
                summary_parts.append(f"{age_hours}h ago")
            else:
                summary_parts.append(f"{age_hours // 24}d ago")
            
            summary_text = " | ".join(summary_parts)
            
            # Update mode usage statistics
            self.statistics['mode_usage']['news'] = self.statistics['mode_usage'].get('news', 0) + 1
            
            news_verse_data = {
                'text': summary_text,
                'reference': f'{source} News',
                'book': 'News',
                'chapter': 0,
                'verse': 0,
                'translation': 'NEWS',
                'is_news_mode': True,
                'news_data': article,
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info("News data retrieved successfully")
            return news_verse_data
            
        except Exception as e:
            self.logger.error(f"Failed to get news data: {e}")
            return {
                'text': f'News service error: {str(e)}',
                'reference': 'News Service Error',
                'book': 'News',
                'chapter': 0,
                'verse': 0,
                'translation': 'ERROR',
                'is_news_mode': True,
                'news_error': True,
                'timestamp': datetime.now().isoformat()
            }
    
    def _get_fallback_news_data(self) -> Dict:
        """Provide fallback news data when news service is unavailable."""
        return {
            'text': 'Israel News Mode | Service temporarily unavailable',
            'reference': 'Bible Clock News',
            'book': 'News',
            'chapter': 0,
            'verse': 0,
            'translation': 'NEWS',
            'is_news_mode': True,
            'news_data': {
                'title': 'News Service Unavailable',
                'description': 'Israel news service is temporarily unavailable. Please try again later.',
                'published': datetime.now(),
                'published_str': datetime.now().strftime("%m/%d %I:%M %p"),
                'source': 'Bible Clock',
                'age_hours': 0
            },
            'timestamp': datetime.now().isoformat()
        }
    
    def _deduplicate_verse_history(self, history: List[Dict]) -> List[Dict]:
        """Remove duplicate verses for the same minute, keeping only the first occurrence."""
        try:
            if not history:
                return history
            
            seen_minutes = set()
            deduplicated = []
            
            # Process in reverse order to keep the most recent entry for each minute
            for entry in reversed(history):
                timestamp = entry.get('timestamp', '')
                if timestamp:
                    # Extract minute from timestamp (YYYY-MM-DD HH:MM)
                    minute_key = timestamp[:16]  # "2025-08-13T11:20" -> "2025-08-13T11:20"
                    
                    if minute_key not in seen_minutes:
                        seen_minutes.add(minute_key)
                        deduplicated.append(entry)
            
            # Reverse back to chronological order
            return list(reversed(deduplicated))
            
        except Exception as e:
            self.logger.warning(f"Verse history deduplication failed: {e}")
            return history

    def _clean_devotional_title(self, title: str) -> str:
        """Clean devotional title by removing 'Faith's Checkbook' and keeping just the subject."""
        import re
        
        if not title:
            return "Today's Devotional"
        
        # Remove "Faith's Checkbook" prefix and clean up the title
        cleaned = title.replace("Faith's Checkbook", "").replace("- ", "").strip()
        
        # If nothing left after cleaning, use a default
        if not cleaned:
            return "Today's Devotional"
        
        # Capitalize first letter if needed
        if cleaned and cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
        
        return cleaned


class VerseScheduler:
    """Handles scheduling of verse updates."""
    
    def __init__(self, verse_manager: VerseManager, update_callback):
        self.verse_manager = verse_manager
        self.update_callback = update_callback
        self.logger = logging.getLogger(__name__)
    
    def schedule_updates(self):
        """Schedule verse updates at the start of each minute."""
        import schedule
        
        schedule.every().minute.at(":00").do(self._update_verse)
        self.logger.info("Verse updates scheduled")
    
    def _update_verse(self):
        """Update the displayed verse."""
        try:
            verse_data = self.verse_manager.get_current_verse()
            self.update_callback(verse_data)
        except Exception as e:
            self.logger.error(f"Verse update failed: {e}")