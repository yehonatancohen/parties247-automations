"""
Real Integration Test for Content Discovery Bot.
Uses TikTokApi to fetch videos with engagement stats automatically.
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Load .env.test from project root
from dotenv import load_dotenv
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
env_test_path = os.path.join(project_root, ".env.test")
if os.path.exists(env_test_path):
    load_dotenv(env_test_path, override=True)
    print(f"📁 Loaded: {env_test_path}")
else:
    load_dotenv()

from config import Config
from models import VideoCandidate, DailyReport
from services.engagement_calculator import EngagementCalculator
from services.tiktok_scraper import TikTokScraper
from services.media_scraper import MediaScraper
from services.follow_suggester import FollowSuggester

Config.ensure_dirs()


async def test_real_tiktok():
    """Test TikTok scraping using yt-dlp."""
    print("\n" + "=" * 60)
    print("📱 TESTING TIKTOK (USING YT-DLP)")
    print("=" * 60)
    
    scraper = TikTokScraper()
    videos = []
    
    # Test with verified public accounts
    test_accounts = [
        "tiktok",           # Official TikTok account
        "charlidamelio",    # Most followed TikToker
    ]
    
    try:
        # Scrape videos from public accounts
        for username in test_accounts:
            print(f"\nFetching videos from @{username}...")
            try:
                user_videos = await scraper.get_user_videos(username, count=3, hours=168) # 7 days
                
                if user_videos:
                    videos.extend(user_videos)
                    print(f"  ✅ Found {len(user_videos)} videos")
                    for v in user_videos[:2]:
                        print(f"     • {v.views:,} views, {v.likes:,} likes")
                        print(f"       URL: {v.video_url}")
                else:
                    print(f"  ⚠️ No recent videos found (or account private/blocked)")
            except Exception as e:
                print(f"  ⚠️ Skipped: {e}")
        
        print(f"\n✅ Total TikTok videos found: {len(videos)}")
        
    except Exception as e:
        print(f"⚠️ TikTok skipped: {e}")
    
    return videos


async def test_real_media():
    """Test Israeli media scraping with real data."""
    print("\n" + "=" * 60)
    print("📰 TESTING ISRAELI MEDIA (REAL DATA)")
    print("=" * 60)
    
    scraper = MediaScraper()
    articles = []
    
    try:
        print("Scanning media sources...")
        for source in Config.MEDIA_SOURCES:
            print(f"  • {source['name']}: {source['url']}")
        
        articles = await scraper.scrape_all_sources()
        print(f"\n✅ Found {len(articles)} party-related articles")
        
        for article in articles[:5]:
            print(f"\n  📰 {article.source}")
            print(f"     {article.title[:70]}...")
            print(f"     Keywords: {', '.join(article.keywords_matched[:3])}")
            print(f"     URL: {article.url}")
        
    except Exception as e:
        print(f"⚠️ Media scraper error: {e}")
    
    finally:
        await scraper.close()
    
    return articles


def analyze_videos(videos: list) -> list:
    """Analyze videos and identify potential hits."""
    print("\n" + "=" * 60)
    print("🧮 ANALYZING VIDEOS FOR POTENTIAL HITS")
    print("=" * 60)
    
    if not videos:
        print("No videos to analyze")
        return []
    
    calc = EngagementCalculator()
    
    for video in videos:
        # Use a default baseline if we don't have one
        baseline = video.baseline_rate if video.baseline_rate > 0 else 5.0
        
        analysis = calc.analyze_video(
            views=video.views,
            likes=video.likes,
            comments=video.comments,
            shares=video.shares,
            followers=video.author_followers,
            baseline=baseline,
            caption=video.caption,
            hashtags=video.hashtags
        )
        
        video.engagement_rate = analysis["engagement_rate"]
        video.potential_score = analysis["potential_score"]
        video.is_potential_hit = analysis["is_potential_hit"]
        video.category = analysis["category"]

    # Sort by potential score
    videos.sort(key=lambda v: v.potential_score, reverse=True)

    # Show results
    potential_hits = [v for v in videos if v.is_potential_hit]
    print(f"\n🔥 POTENTIAL HITS: {len(potential_hits)} (threshold: {Config.POTENTIAL_HIT_THRESHOLD})")

    for video in potential_hits[:10]:
        print(f"\n  🎯 @{video.author_username} ({video.platform})")
        print(f"     Score: {video.potential_score:.2f} | Views: {video.views:,} | Likes: {video.likes:,}")
        print(f"     Engagement: {video.engagement_rate:.2f}%")
        print(f"     Category: {video.category}")
        print(f"     URL: {video.video_url}")
        if video.caption:
            print(f"     Caption: {video.caption[:80]}...")

    if not potential_hits:
        print("\n  No videos above the threshold found.")
        print("\n  📊 Top 5 videos by potential score:")
        for i, video in enumerate(videos[:5], 1):
            print(f"\n  {i}. @{video.author_username}")
            print(f"     Score: {video.potential_score:.2f} | Views: {video.views:,} | Likes: {video.likes:,}")
            print(f"     URL: {video.video_url}")
    
    return videos


def save_results(videos: list, articles: list):
    """Save results to a JSON file."""
    output_file = os.path.join(Config.DATA_DIR, "last_scan_results.json")
    
    results = {
        "scan_time": datetime.now().isoformat(),
        "total_videos": len(videos),
        "potential_hits": len([v for v in videos if v.is_potential_hit]),
        "articles": len(articles),
        "videos": [v.to_dict() for v in videos[:50]],
        "articles_data": [a.to_dict() for a in articles]
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {output_file}")


async def main():
    """Run real integration tests."""
    print("\n" + "=" * 70)
    print("🧪 CONTENT DISCOVERY BOT - REAL INTEGRATION TEST")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"TikTok User: @{Config.TIKTOK_USERNAME}")
    print(f"Potential-Hit Threshold: {Config.POTENTIAL_HIT_THRESHOLD}")
    print(f"Video Age Limit: {Config.VIDEO_AGE_HOURS}h")
    print("\n⚠️ Instagram disabled for this test (IP blocked)")
    
    all_videos = []
    articles = []
    
    # Test TikTok only
    tiktok_videos = await test_real_tiktok()
    all_videos.extend(tiktok_videos)
    
    # Test Media
    articles = await test_real_media()
    
    # Analyze all videos
    analyzed = analyze_videos(all_videos)
    
    # Save results
    save_results(analyzed, articles)
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 FINAL SUMMARY")
    print("=" * 70)
    print(f"  Total videos scanned: {len(all_videos)}")
    print(f"  Potential hits: {len([v for v in analyzed if v.is_potential_hit])}")
    print(f"  Media articles: {len(articles)}")
    print(f"\n  Results saved to: data/last_scan_results.json")


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())
