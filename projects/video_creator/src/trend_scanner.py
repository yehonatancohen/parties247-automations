"""
Trend Scanner - Smart Content Discovery for Parties247

Scans TikTok users for trending videos that match the Parties247 content style:
  - Israeli DJ content (tracks, sets, festival clips)
  - International DJs known in Israel
  - Festival moments, party culture, viral club moments
  - Israeli pride moments (Israeli DJ at big festival, etc.)

3-Layer Scoring Algorithm:
  Layer 1: Content Relevance (50%) - keyword/category matching
  Layer 2: Catchiness / Virality (30%) - engagement metrics
  Layer 3: Technical Quality (20%) - resolution, duration, audio

Two-Phase Scanning:
  Phase 1: Fast scan (metadata only) → Relevance + Catchiness
  Phase 2: Deep scan (top 15 only) → Quality check
  Phase 3: AI classification (top 3 only) → Gemini final verdict

Commands:
  /scan       - Run a manual scan now
  /add        - Add a TikTok username to monitor
  /remove     - Remove a TikTok username
  /watchlist  - Show all monitored users
  /trendshelp - Show help for trend scanner
"""

import os
import sys
import json
import random
import logging
import concurrent.futures
from datetime import datetime, timedelta, time, timezone

import pytz
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackContext,
)

logger = logging.getLogger("trend_scanner")

# ============================================================
# CONFIGURATION
# ============================================================

_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
USERS_FILE = os.path.join(_project_root, "projects", "tiktok_trend_hunter", "users.txt")

if not os.path.exists(USERS_FILE):
    USERS_FILE = os.path.join(_this_dir, "trend_users.txt")
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            f.write("# TikTok usernames to monitor (one per line)\n")

VIDEO_FETCH_LIMIT = 30
SCAN_HOUR = 7
SCAN_MINUTE = 30
TIMEZONE = "Asia/Jerusalem"

# Minimum relevance score to be considered (out of 10)
MIN_RELEVANCE_SCORE = 2.0

# Weights for final score
WEIGHT_RELEVANCE = 0.50
WEIGHT_CATCHINESS = 0.30
WEIGHT_QUALITY = 0.20


# ============================================================
# CONTENT PROFILE - Keywords & Known Artists
# ============================================================

# Each keyword has a weight. Multiple matches stack (capped at 10).
RELEVANCE_KEYWORDS = {
    # DJ mentions (high signal)
    "dj": 2.5,
    "דיג'יי": 2.5,
    "דיגיי": 2.5,
    "דיג׳יי": 2.5,

    # Festival & Events (high signal)
    "festival": 2.5,
    "פסטיבל": 2.5,
    "tomorrowland": 3.0,
    "ultra": 2.5,
    "edc": 2.5,
    "burning man": 2.0,
    "coachella": 2.0,
    "sonar": 2.0,
    "awakenings": 2.5,
    "time warp": 2.5,
    "dreamstate": 2.0,
    "creamfields": 2.0,
    "מסיבה": 2.0,
    "party": 1.5,
    "rave": 2.0,
    "אירוע": 1.5,
    "event": 1.0,
    "lineup": 2.0,
    "לייןאפ": 2.0,

    # Music terms (medium signal)
    "track": 1.5,
    "טראק": 1.5,
    "release": 1.5,
    "רילייס": 1.5,
    "drop": 1.5,
    "דרופ": 1.5,
    "remix": 1.5,
    "רמיקס": 1.5,
    "set": 1.0,
    "סט": 1.0,
    "mix": 1.0,
    "מיקס": 1.0,
    "b2b": 2.0,
    "הופעה": 2.0,
    "live": 1.0,
    "לייב": 1.0,
    "unreleased": 2.0,
    "id": 1.0,
    "bootleg": 1.5,
    "mashup": 1.5,

    # Crowd / Energy (lower signal, but relevant)
    "crowd": 1.0,
    "קהל": 1.0,
    "אנרגיה": 1.0,
    "energy": 1.0,
    "vibe": 0.8,
    "vibes": 0.8,
    "וייב": 0.8,
    "מגה": 1.0,
    "crazy": 0.8,

    # Israeli pride (high signal)
    "ישראלי": 2.0,
    "ישראל": 1.5,
    "israeli": 2.0,
    "israel": 1.5,
    "גאווה": 2.5,
    "pride": 1.5,
    "represent": 1.5,
    "תל אביב": 1.5,
    "tel aviv": 1.5,
    "tlv": 1.0,

    # Genres (low-med signal confirming niche)
    "techno": 1.0,
    "טכנו": 1.0,
    "house": 1.0,
    "האוס": 1.0,
    "trance": 1.5,
    "טראנס": 1.5,
    "psytrance": 1.5,
    "progressive": 1.0,
    "melodic": 1.0,
    "bass": 0.8,
    "edm": 1.0,
    "electronic": 0.8,
    "אלקטרוני": 0.8,
    "minimal": 0.8,
    "afro house": 1.0,
    "indie dance": 1.0,
}

# Israeli DJs/artists (lowercase) - these make content HIGHLY relevant
ISRAELI_ARTISTS = {
    "borgore", "infected mushroom", "vini vici", "astrix", "ace ventura",
    "blastoyz", "neelix", "guy j", "guy mantzur", "chaim",
    "red axes", "autarkic", "canal", "malka tuti",
    "adam ten", "dor danino", "ofeko", "roiko", "yamagucci",
    "genish", "bido", "assaf michael", "itay gat", "dvirn",
    "tal goldbaum", "verso", "mason mamedov", "meir briskman",
    "hunterzezovski", "harushoval", "funkibelski", "avihai levi",
    "rafael", "roei nimni", "ron illouz", "brunello",
    "tetrakord", "anotr", "mellowcircus",
    "solomun",  # Israeli-Bosnian, strongly associated with Israel scene
}

# Top-tier international DJs/artists — only these can pass without Israeli connection
TOP_TIER_INTERNATIONAL = {
    "fisher", "john summit", "johnsummit", "anyma", "rufus du sol",
    "rufusdusol", "mochakk", "mahmut orhan", "prospa",
    "camelphat", "artbat", "tale of us", "amelie lens",
    "charlotte de witte", "peggy gou", "fred again", "skrillex",
    "disclosure", "bicep", "four tet", "jamie jones",
    "the martinez brothers", "marco carola",
    "adam beyer", "nina kraviz", "ben bohmer",
    "black coffee", "keinemusik",
}

# Combined set for general detection
KNOWN_ARTISTS = ISRAELI_ARTISTS | TOP_TIER_INTERNATIONAL

# Keywords that signal Israeli connection
ISRAELI_CONNECTION_KEYWORDS = {
    "ישראלי", "ישראל", "israeli", "israel",
    "תל אביב", "tel aviv", "tlv",
    "גאווה", "pride", "represent",
    "ירושלים", "jerusalem", "eilat", "אילת",
    "haifa", "חיפה", "באר שבע", "beer sheva",
}

# Top-tier international festivals — can pass without Israeli connection
TOP_TIER_FESTIVALS = {
    "tomorrowland", "ultra", "edc", "awakenings", "sonar",
    "time warp", "creamfields", "burning man", "coachella",
    "dreamstate",
}


# ============================================================
# USER LIST MANAGEMENT
# ============================================================

def get_target_users() -> list:
    """Reads usernames from users.txt."""
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def add_user_to_file(username: str) -> tuple:
    """Add a username to users.txt. Returns (success, message)."""
    username = username.strip().lstrip("@").lower()

    if "tiktok.com/" in username:
        parts = username.split("tiktok.com/")
        if len(parts) > 1:
            path = parts[1].split("/")[0].split("?")[0]
            username = path.lstrip("@")

    if not username:
        return False, "❌ Invalid username."

    current = get_target_users()
    if username in current:
        return False, f"ℹ️ @{username} is already in the watchlist."

    with open(USERS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{username}\n")

    return True, f"✅ Added @{username} to watchlist ({len(current) + 1} total users)."


def remove_user_from_file(username: str) -> tuple:
    """Remove a username from users.txt. Returns (success, message)."""
    username = username.strip().lstrip("@").lower()

    if not os.path.exists(USERS_FILE):
        return False, "❌ Users file not found."

    with open(USERS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    found = False
    for line in lines:
        if line.strip().lower() == username:
            found = True
        else:
            new_lines.append(line)

    if not found:
        return False, f"❌ @{username} not found in watchlist."

    with open(USERS_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return True, f"✅ Removed @{username} from watchlist."


# ============================================================
# LAYER 1: CONTENT RELEVANCE SCORING
# ============================================================

def score_relevance(video: dict, username: str) -> tuple:
    """
    Score how relevant a video is to Parties247's content style.
    Returns (score 0-10, detected_category, matched_keywords, is_israeli, is_top_tier).
    
    is_israeli: True if the video has an Israeli connection (Israeli artist,
                Israeli keywords, Hebrew text about Israel, etc.)
    is_top_tier: True if video involves a top-tier international artist/festival
                 (can pass even without Israeli connection)
    """
    description = (video.get('description', '') or '').lower()
    title = (video.get('title', '') or '').lower()
    track = (video.get('track', '') or '').lower()
    artist = (video.get('artist', '') or '').lower()
    
    # Combine all text for keyword matching
    all_text = f"{description} {title} {track} {artist} {username}"
    
    score = 0.0
    matched = []
    is_israeli = False
    is_top_tier = False
    
    # 1. Keyword matching
    for keyword, weight in RELEVANCE_KEYWORDS.items():
        if keyword in all_text:
            score += weight
            matched.append(keyword)
    
    # 2. Israeli connection detection
    # Check if the username is an Israeli artist
    username_clean = username.replace("_", " ").replace(".", " ").lower()
    for artist_name in ISRAELI_ARTISTS:
        if artist_name in all_text or artist_name in username_clean:
            is_israeli = True
            score += 3.0  # Israeli artists get a strong boost
            matched.append(f"🇮🇱 {artist_name}")
            break
    
    # Check for Israeli connection keywords
    if not is_israeli:
        for kw in ISRAELI_CONNECTION_KEYWORDS:
            if kw in all_text:
                is_israeli = True
                score += 2.0
                matched.append(f"🇮🇱 {kw}")
                break
    
    # Check hashtags for Israeli connection
    hashtags = video.get('tags', []) or []
    hashtag_text = ""
    if isinstance(hashtags, list):
        hashtag_text = " ".join(str(h).lower() for h in hashtags)
        if not is_israeli:
            for kw in ISRAELI_CONNECTION_KEYWORDS:
                if kw in hashtag_text:
                    is_israeli = True
                    score += 1.5
                    matched.append(f"🇮🇱#{kw}")
                    break
    
    # 3. Top-tier international detection (can pass without Israeli connection)
    if not is_israeli:
        for artist_name in TOP_TIER_INTERNATIONAL:
            if artist_name in all_text or artist_name in username_clean:
                is_top_tier = True
                score += 2.5
                matched.append(f"🌍 {artist_name}")
                break
        
        if not is_top_tier:
            for fest in TOP_TIER_FESTIVALS:
                if fest in all_text or fest in hashtag_text:
                    is_top_tier = True
                    score += 2.0
                    matched.append(f"🌍 {fest}")
                    break
    
    # 4. General hashtag keyword matching
    if hashtag_text:
        for keyword, weight in RELEVANCE_KEYWORDS.items():
            if keyword in hashtag_text and keyword not in matched:
                score += weight * 0.5
                matched.append(f"#{keyword}")
    
    # Cap at 10
    score = min(score, 10.0)
    
    # Determine category
    category = _classify_category(all_text, matched)
    
    return score, category, matched, is_israeli, is_top_tier


def _classify_category(text: str, matched_keywords: list) -> str:
    """Classify the video into a content category based on matched keywords."""
    matched_set = set(k.lower().lstrip("#🎤 ") for k in matched_keywords)
    
    # Check for Israeli pride content
    israeli_keywords = {"ישראלי", "israeli", "גאווה", "pride", "represent", "ישראל", "israel"}
    festival_keywords = {"festival", "פסטיבל", "tomorrowland", "ultra", "edc", "awakenings", "sonar", "time warp"}
    if israeli_keywords & matched_set and festival_keywords & matched_set:
        return "🇮🇱 Israeli Pride"
    
    # Check for festival/event
    if festival_keywords & matched_set:
        return "🎪 Festival"
    
    # Check for new release
    release_keywords = {"track", "טראק", "release", "רילייס", "unreleased", "id", "remix", "רמיקס", "bootleg", "mashup"}
    if release_keywords & matched_set:
        return "🎵 New Track"
    
    # Check for party/club content
    party_keywords = {"מסיבה", "party", "rave", "אירוע", "event", "crowd", "קהל"}
    if party_keywords & matched_set:
        return "🎧 Party Clip"
    
    # Check for DJ set
    dj_keywords = {"dj", "דיג'יי", "set", "סט", "b2b", "הופעה", "live", "לייב"}
    if dj_keywords & matched_set:
        return "🎧 DJ Set"
    
    # Generic music content
    if matched_set:
        return "🔥 Music"
    
    return "❓ Other"


# ============================================================
# LAYER 2: CATCHINESS / VIRALITY SCORING
# ============================================================

def score_catchiness(video: dict, baseline_avg: float, upload_time=None) -> tuple:
    """
    Score how catchy/viral a video is.
    Returns (score 0-10, details_dict).
    """
    views = video.get('view_count', 0) or 0
    likes = video.get('like_count', 0) or 0
    comments = video.get('comment_count', 0) or 0
    shares = video.get('repost_count', 0) or video.get('share_count', 0) or 0
    
    total_engagement = likes + comments + shares
    engagement_rate = total_engagement / views if views > 0 else 0
    
    details = {
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "engagement_rate": engagement_rate,
    }
    
    score = 0.0
    
    # 1. Engagement ratio vs baseline (0-4 pts)
    if baseline_avg > 0:
        ratio = engagement_rate / baseline_avg
        details["engagement_ratio"] = ratio
        # 2x average = 4 points (linear, capped)
        score += min(ratio * 2, 4.0)
    else:
        details["engagement_ratio"] = 1.0
    
    # 2. View velocity (0-2 pts)
    if upload_time:
        hours_since = max((datetime.now(timezone.utc) - upload_time).total_seconds() / 3600, 1)
        velocity = views / hours_since
        details["velocity"] = velocity
        if velocity >= 1000:
            score += 2.0
        elif velocity >= 500:
            score += 1.5
        elif velocity >= 100:
            score += 1.0
        elif velocity >= 50:
            score += 0.5
    
    # 3. Share ratio (0-2 pts) - shares are the strongest viral signal
    if views > 0:
        share_ratio = shares / views
        details["share_ratio"] = share_ratio
        if share_ratio >= 0.01:  # 1% share rate is exceptional
            score += 2.0
        elif share_ratio >= 0.005:
            score += 1.5
        elif share_ratio >= 0.002:
            score += 1.0
        elif share_ratio >= 0.001:
            score += 0.5
    
    # 4. Absolute views (0-2 pts) - raw popularity signal
    if views >= 500_000:
        score += 2.0
    elif views >= 100_000:
        score += 1.5
    elif views >= 50_000:
        score += 1.0
    elif views >= 10_000:
        score += 0.5
    
    score = min(score, 10.0)
    return score, details


# ============================================================
# LAYER 3: TECHNICAL QUALITY SCORING
# ============================================================

def score_quality(video: dict) -> tuple:
    """
    Score the technical quality of a video.
    Uses full metadata (requires extract_flat=False for detailed info).
    Returns (score 0-10, details_dict).
    """
    details = {}
    score = 0.0
    
    # 1. Video resolution (0-3 pts)
    height = video.get('height') or 0
    width = video.get('width') or 0
    
    # Also check formats list if height not at top level
    if not height and video.get('formats'):
        for fmt in video['formats']:
            h = fmt.get('height') or 0
            if h > height:
                height = h
                width = fmt.get('width', 0)
    
    details["resolution"] = f"{width}x{height}" if height else "unknown"
    if height >= 1080:
        score += 3.0
    elif height >= 720:
        score += 2.0
    elif height >= 480:
        score += 1.0
    # < 480 = 0 pts (trash quality)
    
    # 2. Duration sweet spot (0-3 pts)
    duration = video.get('duration') or 0
    details["duration"] = duration
    if 15 <= duration <= 90:
        score += 3.0   # TikTok sweet spot
    elif 10 <= duration <= 180:
        score += 2.0   # Still good
    elif 5 <= duration <= 300:
        score += 1.0   # Acceptable
    # < 5s or > 300s = 0 pts
    
    # 3. Has original/named sound (0-2 pts)
    track = video.get('track', '')
    artist = video.get('artist', '')
    details["track"] = track or "none"
    details["artist"] = artist or "none"
    if track and artist:
        score += 2.0  # Has identifiable music
    elif track or artist:
        score += 1.0
    
    # 4. Has meaningful description (0-2 pts)
    description = video.get('description', '') or ''
    desc_len = len(description.strip())
    details["desc_length"] = desc_len
    if desc_len >= 50:
        score += 2.0
    elif desc_len >= 10:
        score += 1.0
    
    score = min(score, 10.0)
    return score, details


# ============================================================
# AI CLASSIFICATION (Gemini - top 3 only)
# ============================================================

def classify_with_ai(videos: list) -> list:
    """
    Use Gemini to classify the top 3 videos for final relevance check.
    Modifies videos in-place, adding 'ai_score' and 'ai_reason'.
    Returns the videos sorted by AI-adjusted score.
    """
    try:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.info("No GEMINI_API_KEY, skipping AI classification")
            return videos
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:
        logger.warning(f"Could not initialize Gemini: {e}")
        return videos
    
    # Build a single prompt with all 3 videos
    video_descriptions = []
    for i, v in enumerate(videos[:3]):
        video_descriptions.append(
            f"Video {i+1}:\n"
            f"  Username: @{v.get('username', '?')}\n"
            f"  Description: {(v.get('description', '') or '')[:300]}\n"
            f"  Track: {v.get('track', 'N/A')}\n"
            f"  Artist: {v.get('artist', 'N/A')}\n"
            f"  Views: {v.get('view_count', 0):,}\n"
            f"  Category (auto): {v.get('category', '?')}\n"
            f"  Relevance score (auto): {v.get('relevance_score', 0):.1f}/10\n"
        )
    
    prompt = f"""You are an expert content curator for "Parties 24/7", an Israeli nightlife/DJ TikTok & Instagram page.

The page posts:
- New tracks and releases from Israeli DJs
- Live clips from parties and festivals
- Israeli DJs performing at big international festivals (Israeli pride)
- Big international DJs (known in Israel) playing Israeli DJ tracks
- Festival announcements and special events
- Viral party/rave moments

Rate each video 1-10 on how well it fits this page. Consider:
- Content relevance to the DJ/party scene
- Whether it would interest Israeli nightlife fans ages 16-25
- Repost potential (would followers engage with this?)

Return ONLY valid JSON, no markdown, no explanation:
{{"videos": [
  {{"video": 1, "score": N, "reason": "brief Hebrew reason", "best_pick": true/false}},
  {{"video": 2, "score": N, "reason": "brief Hebrew reason", "best_pick": true/false}},
  {{"video": 3, "score": N, "reason": "brief Hebrew reason", "best_pick": true/false}}
]}}

Here are the videos:

{chr(10).join(video_descriptions)}"""

    try:
        logger.info("🧠 Asking Gemini to classify top 3 videos...")
        response = model.generate_content(prompt)
        
        if not response or not response.text:
            logger.warning("Gemini returned empty response")
            return videos
        
        # Parse JSON response
        text = response.text.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        
        result = json.loads(text)
        ai_videos = result.get("videos", [])
        
        for ai_v in ai_videos:
            idx = ai_v.get("video", 0) - 1
            if 0 <= idx < len(videos):
                videos[idx]["ai_score"] = ai_v.get("score", 5)
                videos[idx]["ai_reason"] = ai_v.get("reason", "")
                videos[idx]["ai_best_pick"] = ai_v.get("best_pick", False)
                
                # Blend AI score into final score (AI gets 15% influence on top candidates)
                current_final = videos[idx].get("final_score", 0)
                ai_boost = (ai_v.get("score", 5) / 10.0) * 1.5  # 0-1.5 range
                videos[idx]["final_score"] = current_final + ai_boost
        
        logger.info("✅ Gemini classification complete")
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse Gemini response: {e}")
    except Exception as e:
        logger.warning(f"Gemini classification error: {e}")
    
    return videos


# ============================================================
# TIKTOK FETCHING (yt-dlp)
# ============================================================

def fetch_videos_yt_dlp(username: str, flat: bool = True) -> list:
    """
    Fetch recent videos for a user using yt-dlp.
    flat=True: Fast extraction (metadata only, for Phase 1)
    flat=False: Full extraction (includes resolution/audio, for Phase 2)
    """
    import time as _time
    _time.sleep(random.uniform(1, 3))
    
    try:
        import yt_dlp
    except ImportError:
        logger.error("yt-dlp not installed")
        return []
    
    url = f"https://www.tiktok.com/@{username}"
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'playlistend': VIDEO_FETCH_LIMIT,
        'socket_timeout': 10,
        'retries': 3,
    }
    
    if flat:
        ydl_opts['extract_flat'] = 'in_playlist'

    for attempt in range(2):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=False)
            if not result:
                return []
            entries = result.get('entries', [])
            return list(entries)
        except Exception as e:
            logger.error(f"Error fetching {username} (attempt {attempt+1}): {e}")
            _time.sleep(3)
    return []


def fetch_single_video_details(video_url: str) -> dict:
    """Fetch full details for a single video (Phase 2)."""
    try:
        import yt_dlp
    except ImportError:
        return {}
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'socket_timeout': 10,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(video_url, download=False)
        return result or {}
    except Exception as e:
        logger.error(f"Error fetching video details: {e}")
        return {}


# ============================================================
# SCANNING PIPELINE
# ============================================================

def process_user_phase1(username: str, cutoff_time) -> list:
    """
    Phase 1: Fast scan for a single user.
    Scores with Layer 1 (Relevance) + Layer 2 (Catchiness).
    Returns list of candidate dicts with scores.
    """
    entries = fetch_videos_yt_dlp(username, flat=True)
    if not entries:
        return []
    
    new_videos = []
    old_engagements = []
    
    for entry in entries:
        ts = entry.get('timestamp')
        if not ts:
            continue
        
        upload_time = datetime.fromtimestamp(ts, tz=timezone.utc)
        views = entry.get('view_count', 0) or 0
        
        if views > 0:
            likes = entry.get('like_count', 0) or 0
            comments = entry.get('comment_count', 0) or 0
            shares = entry.get('repost_count', 0) or entry.get('share_count', 0) or 0
            er = (likes + comments + shares) / views
        else:
            er = 0
        
        if upload_time > cutoff_time:
            entry['_upload_time'] = upload_time
            new_videos.append(entry)
        else:
            old_engagements.append(er)
    
    if not new_videos:
        return []
    
    avg_baseline = sum(old_engagements) / len(old_engagements) if old_engagements else 0.01
    scored = []
    
    for v in new_videos:
        # Layer 1: Relevance (now returns israeli/top-tier flags)
        rel_score, category, keywords, is_israeli, is_top_tier = score_relevance(v, username)
        
        # Skip videos with very low relevance
        if rel_score < MIN_RELEVANCE_SCORE:
            continue
        
        # Layer 2: Catchiness
        catch_score, catch_details = score_catchiness(v, avg_baseline, v.get('_upload_time'))
        
        # ====== ISRAELI PRIORITY GATE ======
        # Israeli content always passes.
        # Non-Israeli content is BLOCKED unless:
        #   - It's exceptionally viral (catchiness >= 7)
        #   - OR it involves a top-tier international artist/festival
        if not is_israeli:
            if not is_top_tier and catch_score < 7.0:
                # Not Israeli, not top-tier, not viral → skip
                continue
        
        # Israeli content gets a final score boost
        israeli_bonus = 1.5 if is_israeli else 0.0
        
        # Phase 1 score (no quality yet, assume average quality = 5)
        phase1_score = (
            rel_score * WEIGHT_RELEVANCE +
            catch_score * WEIGHT_CATCHINESS +
            5.0 * WEIGHT_QUALITY +
            israeli_bonus
        )
        
        v['username'] = username
        v['relevance_score'] = rel_score
        v['catchiness_score'] = catch_score
        v['quality_score'] = 5.0  # Placeholder until Phase 2
        v['category'] = category
        v['is_israeli'] = is_israeli
        v['is_top_tier'] = is_top_tier
        v['matched_keywords'] = keywords[:5]  # Top 5
        v['engagement_ratio'] = catch_details.get('engagement_ratio', 1.0)
        v['final_score'] = phase1_score
        scored.append(v)
    
    return scored


def deep_scan_phase2(candidates: list, limit: int = 15) -> list:
    """
    Phase 2: Deep scan top candidates for technical quality.
    Fetches full video details and applies Layer 3 scoring.
    """
    top = candidates[:limit]
    
    logger.info(f"Phase 2: Deep scanning {len(top)} top candidates...")
    
    for v in top:
        username = v.get('username', '')
        video_id = v.get('id', '')
        
        if not video_id:
            continue
        
        video_url = f"https://www.tiktok.com/@{username}/video/{video_id}"
        
        try:
            details = fetch_single_video_details(video_url)
            if details:
                # Merge useful fields
                for key in ['height', 'width', 'duration', 'formats', 'track', 'artist']:
                    if key in details:
                        v[key] = details[key]
                
                # Layer 3: Quality
                qual_score, qual_details = score_quality(v)
                v['quality_score'] = qual_score
                v['quality_details'] = qual_details
                
                # Recalculate final score with real quality
                israeli_bonus = 1.5 if v.get('is_israeli') else 0.0
                v['final_score'] = (
                    v['relevance_score'] * WEIGHT_RELEVANCE +
                    v['catchiness_score'] * WEIGHT_CATCHINESS +
                    qual_score * WEIGHT_QUALITY +
                    israeli_bonus
                )
        except Exception as e:
            logger.error(f"Phase 2 error for {video_url}: {e}")
    
    # Re-sort by updated final score
    top.sort(key=lambda x: x.get('final_score', 0), reverse=True)
    return top


def run_full_scan() -> list:
    """
    Full scanning pipeline:
    Phase 1: Fast scan all users → Relevance + Catchiness
    Phase 2: Deep scan top 15 → Quality
    Phase 3: AI classify top 3 → Final verdict
    """
    users = get_target_users()
    if not users:
        return []
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    all_candidates = []
    
    # ===== Phase 1: Fast parallel scan =====
    logger.info(f"Phase 1: Scanning {len(users)} users...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_user_phase1, user, cutoff): user for user in users}
        for future in concurrent.futures.as_completed(futures):
            user = futures[future]
            try:
                candidates = future.result()
                if candidates:
                    all_candidates.extend(candidates)
                    logger.info(f"  {user}: {len(candidates)} relevant videos")
            except Exception as exc:
                logger.error(f"  {user}: error - {exc}")
    
    if not all_candidates:
        logger.info("Phase 1: No relevant videos found.")
        return []
    
    # Sort by Phase 1 score
    all_candidates.sort(key=lambda x: x.get('final_score', 0), reverse=True)
    logger.info(f"Phase 1 complete: {len(all_candidates)} candidates found")
    
    # ===== Phase 2: Deep scan top 15 =====
    top_candidates = deep_scan_phase2(all_candidates, limit=15)
    logger.info(f"Phase 2 complete: {len(top_candidates)} videos quality-checked")
    
    # ===== Phase 3: AI classification of top 3 =====
    if len(top_candidates) >= 1:
        top_candidates = classify_with_ai(top_candidates)
        # Re-sort after AI adjustment
        top_candidates.sort(key=lambda x: x.get('final_score', 0), reverse=True)
        logger.info("Phase 3 complete: AI classification done")
    
    return top_candidates


# ============================================================
# OUTPUT FORMATTING
# ============================================================

def format_scan_results(videos: list, limit: int = 10) -> str:
    """Format scan results as a rich Telegram message."""
    if not videos:
        return "📭 No relevant trending videos found in the last 24 hours."
    
    top = videos[:limit]
    lines = [f"🔥 *Top {len(top)} Trending Videos* 🔥\n"]
    
    for i, v in enumerate(top, 1):
        username = v.get('username', '?')
        video_id = v.get('id', '')
        views = v.get('view_count', 0) or 0
        category = v.get('category', '?')
        rel_score = v.get('relevance_score', 0)
        catch_score = v.get('catchiness_score', 0)
        qual_score = v.get('quality_score', 5)
        final_score = v.get('final_score', 0)
        ratio = v.get('engagement_ratio', 0)
        url = f"https://www.tiktok.com/@{username}/video/{video_id}"
        desc = (v.get('description', '') or '')[:80]
        
        # Connection badge
        connection = ""
        if v.get('is_israeli'):
            connection = " 🇮🇱"
        elif v.get('is_top_tier'):
            connection = " 🌍"
        
        # AI badge
        ai_badge = ""
        if v.get('ai_best_pick'):
            ai_badge = " 🤖✨"
        elif v.get('ai_score'):
            ai_badge = f" 🤖{v['ai_score']}/10"
        
        # Score breakdown
        score_bar = f"R:{rel_score:.0f} C:{catch_score:.0f} Q:{qual_score:.0f}"
        
        lines.append(
            f"{i}.{connection} {category} *@{username}*{ai_badge}\n"
            f"   📊 Score: {final_score:.1f} ({score_bar})\n"
            f"   📈 {ratio:.1f}x avg | 👁 {views:,} views\n"
            f"   {desc}\n"
            f"   [Watch]({url})\n"
        )
        
        # Show AI reason if available
        ai_reason = v.get('ai_reason', '')
        if ai_reason:
            lines.append(f"   💬 _{ai_reason}_\n")
    
    total_users = len(get_target_users())
    lines.append(f"\n📊 Scanned {total_users} users | {len(videos)} relevant videos found")
    
    return "\n".join(lines)


# ============================================================
# TELEGRAM COMMAND HANDLERS
# ============================================================

def _is_allowed(user_id: int) -> bool:
    """Check if user is allowed."""
    allowed_id = os.getenv("ALLOWED_USER_ID")
    allowed_ids = os.getenv("ALLOWED_USER_IDS", "")

    allowed = set()
    if allowed_id:
        try:
            allowed.add(int(allowed_id))
        except ValueError:
            pass
    for uid in allowed_ids.split(","):
        uid = uid.strip()
        if uid:
            try:
                allowed.add(int(uid))
            except ValueError:
                pass

    return not allowed or user_id in allowed


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan - run a trend scan now."""
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Access denied.")
        return

    users = get_target_users()
    status = await update.message.reply_text(
        f"🔍 *Smart Scan Starting*\n\n"
        f"📊 Phase 1: Scanning {len(users)} users (fast)...\n"
        f"🔬 Phase 2: Deep quality check (top 15)...\n"
        f"🤖 Phase 3: AI classification (top 3)...\n\n"
        f"⏳ This may take 5-10 minutes.",
        parse_mode="Markdown"
    )

    try:
        import asyncio
        results = await asyncio.to_thread(run_full_scan)
        message = format_scan_results(results)

        # Split long messages
        if len(message) > 4000:
            parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)

        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status.message_id)
        except Exception:
            pass

    except Exception as e:
        await update.message.reply_text(f"❌ Scan failed: {str(e)}")
        logger.error(f"Scan error: {e}", exc_info=True)


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add <username_or_link> - add user to watchlist."""
    if not _is_allowed(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /add <username or TikTok link>\n\n"
            "Examples:\n"
            "  /add johnsummit\n"
            "  /add https://www.tiktok.com/@johnsummit"
        )
        return

    input_str = context.args[0]
    success, msg = add_user_to_file(input_str)
    await update.message.reply_text(msg)


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remove <username> - remove user from watchlist."""
    if not _is_allowed(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /remove <username>")
        return

    success, msg = remove_user_from_file(context.args[0])
    await update.message.reply_text(msg)


async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /watchlist - show all monitored users."""
    if not _is_allowed(update.effective_user.id):
        return

    users = get_target_users()
    if not users:
        await update.message.reply_text("📭 Watchlist is empty. Use /add to add users.")
        return

    lines = [f"👁 *Watchlist* ({len(users)} users)\n"]
    for i, user in enumerate(users, 1):
        lines.append(f"{i}. @{user}")

    msg = "\n".join(lines)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n..."

    await update.message.reply_text(msg, parse_mode="Markdown")


async def trends_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trendshelp - show trend scanner help."""
    if not _is_allowed(update.effective_user.id):
        return

    await update.message.reply_text(
        "🔍 *Smart Trend Scanner*\n\n"
        "*Commands:*\n"
        "/scan - Run a full smart scan (3 phases)\n"
        "/add <user> - Add a TikTok username or link\n"
        "/remove <user> - Remove from monitoring\n"
        "/watchlist - Show all monitored users\n"
        "/trendshelp - Show this help\n\n"
        "*How it works:*\n"
        "1️⃣ Scans all users for new videos\n"
        "2️⃣ Scores relevance (DJ/party content)\n"
        "3️⃣ Checks engagement & virality\n"
        "4️⃣ Deep quality check on top 15\n"
        "5️⃣ AI picks the best from top 3\n\n"
        f"📅 Auto scan: {SCAN_HOUR:02d}:{SCAN_MINUTE:02d} Israel time\n"
        f"👁 Monitoring {len(get_target_users())} users",
        parse_mode="Markdown"
    )


# ============================================================
# SCHEDULED JOB
# ============================================================

async def daily_scan_job(context: CallbackContext):
    """Scheduled daily scan job."""
    import asyncio
    logger.info("Running scheduled daily trend scan...")

    try:
        results = await asyncio.to_thread(run_full_scan)
        message = format_scan_results(results, limit=5)

        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        header = f"📅 *Daily Trend Report* - {now.strftime('%d/%m/%Y')}\n\n"
        message = header + message

        allowed_id = os.getenv("ALLOWED_USER_ID")
        allowed_ids = os.getenv("ALLOWED_USER_IDS", "")

        recipients = set()
        if allowed_id:
            try:
                recipients.add(int(allowed_id))
            except ValueError:
                pass
        for uid in allowed_ids.split(","):
            uid = uid.strip()
            if uid:
                try:
                    recipients.add(int(uid))
                except ValueError:
                    pass

        for user_id in recipients:
            try:
                if len(message) > 4000:
                    parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
                    for part in parts:
                        await context.bot.send_message(user_id, part, parse_mode="Markdown", disable_web_page_preview=True)
                else:
                    await context.bot.send_message(user_id, message, parse_mode="Markdown", disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Failed to send report to {user_id}: {e}")

    except Exception as e:
        logger.error(f"Daily scan failed: {e}")


# ============================================================
# SETUP (called by main bot)
# ============================================================

async def setup_trend_scanner(application: Application):
    """
    Register trend scanner handlers and schedule daily job.
    Called by the main parties247 bot during initialization.
    """
    print("=" * 50)
    print("🔍 Setting up Smart Trend Scanner")
    print("=" * 50)

    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("watchlist", watchlist_command))
    application.add_handler(CommandHandler("trendshelp", trends_help_command))

    tz = pytz.timezone(TIMEZONE)
    scan_time = time(hour=SCAN_HOUR, minute=SCAN_MINUTE, tzinfo=tz)

    application.job_queue.run_daily(
        daily_scan_job,
        time=scan_time,
        name="daily_trend_scan"
    )

    users_count = len(get_target_users())
    print(f"  📅 Daily scan: {SCAN_HOUR:02d}:{SCAN_MINUTE:02d} {TIMEZONE}")
    print(f"  👁 Monitoring: {users_count} TikTok users")
    print(f"  📄 Users file: {USERS_FILE}")
    print(f"  🧠 AI: Gemini {'available' if os.getenv('GEMINI_API_KEY') else 'not configured'}")
    print(f"  🎯 Min relevance: {MIN_RELEVANCE_SCORE}/10")
    print("🔍 Smart Trend Scanner ready!")
