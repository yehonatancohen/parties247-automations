"""
Israeli Media Scraper for Content Discovery Bot.

Monitors Israeli news and entertainment sites for party-related content.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False

from config import Config
from models import MediaArticle


class MediaScraper:
    """Scrapes Israeli media for party-related news."""
    
    def __init__(self):
        self.sources = Config.MEDIA_SOURCES
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Combined keywords (Hebrew and English)
        self.keywords = [
            # Hebrew
            "מסיבה", "מסיבות", "טראנס", "אלקטרוני", "פסטיבל", "DJ", "דיג'יי",
            "הופעה", "מועדון", "ריקודים", "טכנו", "האוס", "רייב",
            # English
            "party", "rave", "festival", "edm", "techno", "trance", "house",
            "dj", "club", "nightlife", "electronic music", "dance"
        ]
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def scrape_all_sources(self) -> List[MediaArticle]:
        """
        Scrape all configured media sources.
        
        Returns:
            List of MediaArticle objects
        """
        all_articles = []
        
        for source in self.sources:
            try:
                if source.get("type") == "rss":
                    articles = await self._scrape_rss(source)
                else:
                    articles = await self._scrape_webpage(source)
                
                all_articles.extend(articles)
                
            except Exception as e:
                print(f"❌ Error scraping {source['name']}: {e}")
        
        print(f"📰 Media: Found {len(all_articles)} party-related articles")
        return all_articles
    
    async def _scrape_rss(self, source: dict) -> List[MediaArticle]:
        """Scrape an RSS feed."""
        if not FEEDPARSER_AVAILABLE:
            return []
        
        articles = []
        
        try:
            session = await self._get_session()
            async with session.get(source["url"]) as response:
                content = await response.text()
            
            feed = feedparser.parse(content)
            
            for entry in feed.entries[:20]:  # Check last 20 entries
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                
                # Check for keyword matches
                text = f"{title} {summary}".lower()
                matched = [kw for kw in source.get("keywords", self.keywords) 
                          if kw.lower() in text]
                
                if matched:
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6])
                    
                    articles.append(MediaArticle(
                        source=source["name"],
                        title=title,
                        url=link,
                        published_at=published,
                        summary=summary[:300],
                        keywords_matched=matched
                    ))
        
        except Exception as e:
            print(f"RSS scrape error for {source['name']}: {e}")
        
        return articles
    
    async def _scrape_webpage(self, source: dict) -> List[MediaArticle]:
        """Scrape a webpage for articles."""
        articles = []
        
        try:
            session = await self._get_session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with session.get(source["url"], headers=headers) as response:
                if response.status != 200:
                    return []
                content = await response.text()
            
            soup = BeautifulSoup(content, "lxml")
            
            # Find article links - common patterns
            article_selectors = [
                "article a",
                ".article-card a",
                ".post-title a",
                "h2 a", "h3 a",
                ".story-link",
                ".news-item a"
            ]
            
            seen_urls = set()
            
            for selector in article_selectors:
                for link in soup.select(selector)[:30]:
                    href = link.get("href")
                    if not href:
                        continue
                    
                    # Make absolute URL
                    url = urljoin(source["url"], href)
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    # Get title
                    title = link.get_text(strip=True)
                    if not title or len(title) < 10:
                        continue
                    
                    # Check for keyword matches
                    text = title.lower()
                    matched = [kw for kw in source.get("keywords", self.keywords)
                              if kw.lower() in text]
                    
                    if matched:
                        articles.append(MediaArticle(
                            source=source["name"],
                            title=title,
                            url=url,
                            published_at=datetime.now(),  # Approximate
                            summary="",
                            keywords_matched=matched
                        ))
        
        except Exception as e:
            print(f"Webpage scrape error for {source['name']}: {e}")
        
        return articles
    
    async def search_for_topic(self, topic: str) -> List[MediaArticle]:
        """
        Search for a specific topic across sources.
        
        Args:
            topic: Search term
        
        Returns:
            List of matching articles
        """
        all_articles = await self.scrape_all_sources()
        
        # Filter by topic
        topic_lower = topic.lower()
        return [
            a for a in all_articles
            if topic_lower in a.title.lower() or topic_lower in a.summary.lower()
        ]


# Additional Israeli sources to potentially add
ADDITIONAL_SOURCES = [
    {
        "name": "Secret Tel Aviv",
        "url": "https://secrettelaviv.com/best/nightlife-parties",
        "type": "scrape"
    },
    {
        "name": "Time Out TLV",
        "url": "https://www.timeout.com/israel/nightlife",
        "type": "scrape"
    }
]


# Test
if __name__ == "__main__":
    async def test():
        scraper = MediaScraper()
        
        try:
            print("Scanning Israeli media for party content...")
            articles = await scraper.scrape_all_sources()
            
            for article in articles[:5]:
                print(f"\n📰 {article.source}: {article.title}")
                print(f"   URL: {article.url}")
                print(f"   Keywords: {', '.join(article.keywords_matched)}")
        
        finally:
            await scraper.close()
    
    asyncio.run(test())
