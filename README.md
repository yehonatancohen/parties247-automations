# 🎥 Parties247 AutoContent Bot

An automated pipeline for generating high-quality "News Style" vertical videos for TikTok, Instagram Reels, and YouTube Shorts. The bot fetches video content, applies a branded graphic overlay with Hebrew text support, generates viral AI descriptions, and processes everything for optimal engagement.

## 🚀 Features
* **Multi-Platform Support:** Advanced video fetching from TikTok, Instagram, and YouTube.
* **Stealth TikTok Downloader:** Uses Playwright browser automation to bypass bot detection.
* **AI-Powered Captions:** Automatically generates viral Hebrew descriptions using Google's **Gemini 1.5 Flash**.
* **Pro Graphics Engine:**
    * Resizes content to 9:16 (1080x1920) aspect ratio.
    * Generates a full-screen blurred background to eliminate black bars.
    * Applies a custom branded wooden sign overlay.
    * **Opaque Backing:** Smart layer logic prevents video/text bleed-through behind the banner.
* **Hebrew & Emoji Support:** Full RTL (Right-to-Left) rendering with correct emoji positioning.
* **Dual Layout Modes:** 
    * `Standard`: Centered video.
    * `Lower`: Crops the top (to hide original captions) and centers the video lower for better clarity.
* **Docker Ready:** Deploy easily anywhere with containerization.

## ⚙️ Setup & Installation

### 1. Requirements
* Python 3.12+
* [FFmpeg](https://ffmpeg.org/) (System dependency for video processing)
* [Playwright](https://playwright.dev/) (For TikTok bypass)

### 2. Manual Installation
```bash
git clone <repo_url>
cd parties247-automations
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```ini
TELEGRAM_TOKEN=your_bot_token_here
ALLOWED_USER_ID=your_id_here
GEMINI_API_KEY=your_google_ai_key_here
```

## 🐳 Docker Deployment (Recommended)
The easiest way to run the bot with all dependencies (FFmpeg, Chromium, etc.) correctly configured.

1. **Build:**
   ```bash
   docker build -t parties-bot .
   ```
2. **Run:**
   ```bash
   docker run -d --name parties-bot --env-file .env -v ${PWD}/src/output:/app/output parties-bot
   ```

## 🤖 Usage
1. Start the bot in Telegram with `/start`.
2. **Send Link:** Paste the TikTok/Instagram/YouTube URL.
3. **Send Title:** The large text that appears on the wooden sign.
4. **Send Body:** The sub-text for the sign.
5. **Choose Layout:** Select between Standard or Lower (for TikToks with captions).
6. **Wait:** The bot will download, design, and render the video, then send it back with an AI-generated viral caption.

## 🧪 Testing
This project includes a test script to quickly check the overlay generation without running the full video processing pipeline.

### Running the Overlay Test
To test the overlay creation, run the following command from the root directory:
```bash
python tests/test_overlay.py
```
This will generate an `overlay.png` file in the `src/temp` directory. You can inspect this file to verify the appearance of the headline and body text on the overlay.

## 🛠️ Project Structure
```text
parties247-automations/
├── src/
│   ├── main.py             # Bot entry point & conversation logic
│   ├── config.py           # Paths and settings
│   ├── assets/             # Branding images & fonts
│   └── services/
│       ├── ai_generator.py # Gemini AI caption logic
│       ├── downloader.py   # Stealth Playwright/yt-dlp logic
│       ├── graphics.py     # MoviePy rendering engine
│       └── text_utils.py   # Hebrew RTL handling
├── tests/
│   └── test_overlay.py     # Test script for overlay generation
├── Dockerfile              # Container configuration
└── requirements.txt        # Python dependencies
```

## 📦 Core Dependencies
* `moviepy`: Video editing & compositing.
* `google-generativeai`: Gemini 1.5 Flash integration.
* `playwright`: Headless browser automation.
* `python-telegram-bot`: Interactive CLI/Chat interface.
* `Pillow` & `pilmoji`: High-quality image processing with emoji support.