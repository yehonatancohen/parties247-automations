# 🎥 AutoContent Bot - Social Media Automation

An automated pipeline for generating "News Style" vertical videos for TikTok, Instagram Reels, and YouTube Shorts. The bot fetches video content, applies a branded graphic overlay with Hebrew text support, and processes the video for optimal engagement.

## 🚀 Features
* **Video Downloading:** Automatic fetching from various platforms (TikTok, YouTube, etc.) using `yt-dlp`.
* **Smart Rendering:**
    * Resizes content to 9:16 aspect ratio.
    * Generates a blurred, darkened background to fill empty space.
    * Applies a custom PNG overlay (e.g., wooden sign).
* **Hebrew Support:** Full RTL (Right-to-Left) text rendering using `python-bidi` and `arabic-reshaper`.
* **Telegram Interface:** Control the entire process via a simple Telegram chat bot.
* **Scalable Architecture:** Micro-service style structure (Downloader, Graphics, Text Utils).

## 🛠️ Project Structure
```text
/auto_content_bot
│
├── .env                    # Secrets (Token, User ID)
├── main.py                 # Telegram Bot Entry Point
├── config.py               # Configuration & Paths
├── requirements.txt        # Python Dependencies
├── assets/                 # Static files
│   ├── wood_sign.png       # The overlay image
│   └── fonts/              # .ttf files supporting Hebrew
└── services/
    ├── downloader.py       # Video fetching logic
    ├── graphics.py         # Image & Video rendering engine
    └── text_utils.py       # RTL text processing

```

## ⚙️ Setup & Installation

### 1. Clone & Install

```bash
git clone <repo_url>
cd auto_content_bot
pip install -r requirements.txt

```

*Note: Ensure you have [ImageMagick](https://imagemagick.org/) installed if running on Windows (required for MoviePy).*

### 2. Assets Configuration

* Place your overlay image in `assets/wood_sign.png`.
* Place Hebrew supporting fonts (Bold & Regular) in `assets/fonts/`.
* Update paths in `config.py` if filenames differ.

### 3. Environment Variables

Create a `.env` file in the root directory:

```ini
TELEGRAM_TOKEN=your_bot_token_here
ALLOWED_USER_ID=123456789

```

## 🤖 Usage

Run the bot:

```bash
python main.py

```

**Telegram Command Format:**
Send a message to your bot in the following format:

```text
Video URL | Title Text | Body Text
```

**Example:**
`https://www.tiktok.com/@user/video/123 | מסיבה בחיפה! | הדיג'יי הכי חזק מגיע לרוממה בחמישי הקרוב`

## 📦 Requirements

* Python 3.9+
* moviepy
* Pillow
* python-telegram-bot
* yt-dlp
* python-bidi
* arabic-reshaper