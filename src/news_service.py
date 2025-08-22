"""
News Service - Fetches recent news articles about Israel for Bible Clock display.
Provides cycling news content with titles, summaries, and timestamps.
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import time


class NewsService:
    """Handles news data retrieval and caching."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # News API configuration
        self.news_api_url = "https://newsapi.org/v2/everything"
        self.api_key = None  # Will use free tier for now
        
        # Multiple RSS sources with higher memory budget
        self.rss_sources = [
            "https://www.timesofisrael.com/feed/",  # Times of Israel main feed
            "https://www.jpost.com/rss/rssfeedsheadlines.aspx",  # Jerusalem Post headlines
        ]
        
        # Cache settings - optimized for 650MB memory limit
        self.cache_duration = 1800  # 30 minutes
        self.last_update = 0
        self.cached_articles = []
        self.max_cached_articles = 8  # More stories with higher memory limit
        
        # Article cycling
        self.current_article_index = 0
        self.article_display_duration = 30  # 30 seconds per article
        self.last_article_change = 0
    
    def get_israel_news(self, force_refresh: bool = False) -> List[Dict]:
        """Get recent news articles about Israel."""
        current_time = time.time()
        
        # Check if we need to refresh
        if (not self.cached_articles or 
            current_time - self.last_update > self.cache_duration or 
            force_refresh):
            
            self.logger.info("Fetching fresh Israel news...")
            self._fetch_news_articles()
            self.last_update = current_time
        
        return self.cached_articles
    
    def get_current_article(self) -> Optional[Dict]:
        """Get the current article to display (cycling through articles)."""
        articles = self.get_israel_news()
        
        if not articles:
            return None
        
        current_time = time.time()
        
        # Check if it's time to cycle to next article
        if (current_time - self.last_article_change > self.article_display_duration):
            self.current_article_index = (self.current_article_index + 1) % len(articles)
            self.last_article_change = current_time
            self.logger.info(f"Cycling to article {self.current_article_index + 1} of {len(articles)}")
        
        return articles[self.current_article_index]
    
    def reset_to_first_article(self):
        """Reset to the first article when starting news mode."""
        self.current_article_index = 0
        self.last_article_change = time.time()
        self.logger.info("Reset news display to first article")
    
    def _fetch_news_articles(self):
        """Fetch news articles from various sources with memory management."""
        import gc
        
        try:
            # Clear old cached articles and force garbage collection
            old_articles_count = len(self.cached_articles)
            self.cached_articles.clear()
            gc.collect()
            self.logger.info(f"Cleared {old_articles_count} old articles from cache")
            
            # Try RSS feeds first (no API key required)
            articles = self._fetch_from_rss()
            
            if not articles:
                # Fallback to free news sources
                articles = self._fetch_from_free_sources()
            
            if articles:
                # Clean and format articles with memory management
                self.cached_articles = self._process_articles(articles)
                self.logger.info(f"Successfully cached {len(self.cached_articles)} Israel news articles")
                
                # Clear temporary articles list and force cleanup
                articles.clear()
                del articles
                gc.collect()
                
                # Log memory usage after processing
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                self.logger.info(f"News service memory after fetch: {memory_mb:.1f}MB")
            else:
                self.cached_articles = self._get_fallback_news()
            
        except Exception as e:
            self.logger.error(f"Error fetching news: {e}")
            # Provide fallback news if fetch fails
            self.cached_articles = self._get_fallback_news()
            
        finally:
            # Always ensure garbage collection happens
            gc.collect()
    
    def _fetch_from_rss(self) -> List[Dict]:
        """Fetch articles from RSS feeds with memory optimization."""
        import gc
        articles = []
        
        try:
            import feedparser
            
            for rss_url in self.rss_sources:
                try:
                    self.logger.info(f"Fetching from RSS: {rss_url}")
                    
                    # Set user agent and memory-efficient parsing
                    feed = feedparser.parse(rss_url, 
                                          agent='Bible-Clock-News/1.0 (+https://github.com/anthropics/claude-code)')
                    
                    if not feed.entries:
                        self.logger.warning(f"No entries found in {rss_url}")
                        del feed
                        gc.collect()
                        continue
                    
                    source_name = self._get_source_name(rss_url, feed)
                    processed_count = 0
                    
                    # Process up to max_cached_articles entries, but filter for relevance
                    for entry in feed.entries[:self.max_cached_articles * 2]:  # Get more to filter from
                        if processed_count >= self.max_cached_articles:
                            break
                            
                        # Filter for Israel-related content if from general feeds
                        if self._is_israel_relevant(entry, rss_url):
                            # Create minimal article object to save memory
                            title = entry.get('title', 'No title')[:150]  # Limit title length
                            description = entry.get('summary', entry.get('description', ''))[:200]  # Limit description
                            
                            article = {
                                'title': title.strip(),
                                'description': description.strip(),
                                'published': entry.get('published', entry.get('updated', '')),
                                'link': entry.get('link', ''),
                                'source': source_name
                            }
                            articles.append(article)
                            processed_count += 1
                            
                            # Clear entry reference to free memory
                            del entry
                    
                    # Clean up feed object after processing
                    del feed
                    gc.collect()
                    self.logger.info(f"Processed {processed_count} articles from {source_name}")
                        
                except Exception as e:
                    self.logger.warning(f"Failed to fetch from {rss_url}: {e}")
                    # Ensure cleanup even on error
                    gc.collect()
                    continue
                    
        except ImportError:
            self.logger.warning("feedparser not available, skipping RSS feeds")
        
        return articles
    
    def _get_source_name(self, rss_url: str, feed) -> str:
        """Get a clean source name from the RSS feed."""
        if 'timesofisrael' in rss_url:
            return 'Times of Israel'
        elif 'jpost' in rss_url:
            return 'Jerusalem Post'
        elif 'haaretz' in rss_url:
            return 'Haaretz'
        elif 'reuters' in rss_url:
            return 'Reuters'
        elif 'israel21c' in rss_url:
            return 'Israel21c'
        else:
            # Fallback to feed title
            return feed.feed.get('title', 'Israel News')[:30]  # Limit length
    
    def _is_israel_relevant(self, entry, rss_url: str) -> bool:
        """Check if an article is relevant to Israel."""
        # Israel-specific sources are always relevant
        if any(source in rss_url for source in ['timesofisrael', 'jpost', 'haaretz', 'israel21c']):
            return True
        
        # For general sources like Reuters, filter for Israel content
        israel_keywords = [
            'israel', 'israeli', 'jerusalem', 'tel aviv', 'gaza', 'west bank',
            'netanyahu', 'knesset', 'idf', 'hebew', 'jewish', 'palestine',
            'middle east', 'syria border', 'lebanon'
        ]
        
        title = entry.get('title', '').lower()
        description = entry.get('summary', entry.get('description', '')).lower()
        
        # Check if any Israel-related keywords appear in title or description
        content = f"{title} {description}"
        return any(keyword in content for keyword in israel_keywords)
    
    def _fetch_from_free_sources(self) -> List[Dict]:
        """Fetch from free news sources (fallback only)."""
        # This is now just a fallback - primary source is RSS feeds
        return []
    
    def _process_articles(self, raw_articles: List[Dict]) -> List[Dict]:
        """Clean and format articles for display with memory optimization."""
        import re
        import gc
        processed = []
        
        # Pre-compile regex for efficiency
        html_tag_pattern = re.compile('<[^<]+?>')
        
        for article in raw_articles[:self.max_cached_articles]:  # Limit cached articles
            try:
                # Clean title with length limit
                title = article.get('title', 'No title')
                title = title.strip()[:120]  # Slightly longer for better readability
                
                # Clean description with HTML tag removal
                description = article.get('description', '')
                if description:
                    # Remove HTML tags efficiently
                    description = html_tag_pattern.sub('', description)
                    description = description.strip()[:150]  # Reasonable description length
                
                # Parse published date
                published_str = article.get('published', '')
                try:
                    if published_str:
                        # Handle various RSS date formats
                        import email.utils
                        # Try RFC 2822 format first (common in RSS)
                        try:
                            time_tuple = email.utils.parsedate_tz(published_str)
                            if time_tuple:
                                import calendar
                                timestamp = calendar.timegm(time_tuple)
                                published = datetime.fromtimestamp(timestamp)
                            else:
                                raise ValueError("Could not parse date")
                        except:
                            # Fallback to ISO format
                            published = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                    else:
                        published = datetime.now()
                except Exception as e:
                    self.logger.debug(f"Date parsing failed for '{published_str}': {e}")
                    published = datetime.now()
                
                processed_article = {
                    'title': title,
                    'description': description,
                    'published': published,
                    'published_str': published.strftime("%m/%d %I:%M %p"),
                    'source': article.get('source', 'Israel News'),
                    'age_hours': int((datetime.now() - published).total_seconds() / 3600)
                }
                
                processed.append(processed_article)
                
            except Exception as e:
                self.logger.warning(f"Error processing article: {e}")
                continue
        
        # Sort by published date (newest first)
        processed.sort(key=lambda x: x['published'], reverse=True)
        
        return processed
    
    def _get_fallback_news(self) -> List[Dict]:
        """Provide fallback news when fetch fails."""
        return [
            {
                'title': 'Israel News Update',
                'description': 'Stay informed with the latest news from Israel. News service temporarily unavailable.',
                'published': datetime.now(),
                'published_str': datetime.now().strftime("%m/%d %I:%M %p"),
                'source': 'Bible Clock News',
                'age_hours': 0
            }
        ]


# Create global instance
news_service = NewsService()