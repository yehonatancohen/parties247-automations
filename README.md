# 🎉 Parties247 Automation Suite

A collection of automation projects for nightlife/event promotion content. All projects run concurrently through a unified Docker setup.

## 📦 Projects

### 1. 🎥 Video Creator (`projects/video_creator/`)
An automated pipeline for generating high-quality "News Style" vertical videos for TikTok, Instagram Reels, and YouTube Shorts. The bot fetches video content, applies a branded graphic overlay with Hebrew text support, generates viral AI descriptions, and processes everything for optimal engagement.

**Features:**
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

### 2. 📸 Instagram Stories (`projects/instagram_stories/`)
Automated Instagram story uploads with link stickers for event promotion.

**Features:**
* **Telegram Bot Interface**: Schedule story uploads via Telegram commands
* **Natural Language Scheduling**: Supports Hebrew and English schedule inputs
  * `היום 18:00` / `today 18:00` - Upload today at specific time
  * `מחר 10:00` / `tomorrow 10:00` - Upload tomorrow
  * `ראשון 20:00` / `sunday 20:00` - Upload on a specific day
  * `כל ראשון 18:00` / `every sunday 18:00` - Recurring weekly
  * `כל יום 09:00` / `every day 09:00` - Recurring daily
  * `3 פעמים השבוע` / `3 times this week` - Auto-distributed
  * `15/02 20:00` - Specific date
* **Link Stickers**: Add clickable link stickers to stories
* **Hebrew Text Overlay**: Auto-generates "קנה כאן 🛒" text on images
* **Persistent Scheduling**: SQLite storage survives bot restarts
* **Session Persistence**: Instagram login saved for future use

**Commands:**
* `/story` - Schedule a new story upload
* `/mystories` - View your scheduled stories
* `/cancelstory` - Cancel a scheduled story
* `/help` - Show help

---

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
Create a `.env` file in each project's `src/` directory:

**Video Creator** (`projects/video_creator/src/.env`):
```ini
TELEGRAM_TOKEN=your_bot_token_here
ALLOWED_USER_ID=your_id_here
GEMINI_API_KEY=your_google_ai_key_here
```

**Instagram Stories** (`projects/instagram_stories/src/.env`):
```ini
# Use a SEPARATE Telegram bot for this project
IG_TELEGRAM_TOKEN=your_instagram_stories_bot_token
ALLOWED_USER_ID=your_telegram_user_id

# Instagram Login
INSTAGRAM_USERNAME=your_instagram_username
INSTAGRAM_PASSWORD=your_instagram_password
```

---

## 🐳 Docker Deployment (Recommended)

The easiest way to run all automation projects with all dependencies (FFmpeg, Chromium, etc.) correctly configured.

1. **Build:**
   ```bash
   docker build -t parties-bot .
   ```

2. **Run:**
   ```bash
   docker run -d --name parties-bot \
     --env-file projects/video_creator/src/.env \
     -v ${PWD}/projects/video_creator/src/output:/app/projects/video_creator/src/output \
     parties-bot
   ```

---

## 🚀 Running Locally

### Run All Projects
```bash
python run_all.py
```

### Run Individual Project
```bash
# Video Creator
cd projects/video_creator/src && python main.py

# Instagram Stories
cd projects/instagram_stories/src && python main.py
```

---

## 🤖 Usage

### Video Creator
1. Start the bot in Telegram with `/start`.
2. **Send Link:** Paste the TikTok/Instagram/YouTube URL.
3. **Send Title:** The large text that appears on the wooden sign.
4. **Send Body:** The sub-text for the sign.
5. **Choose Layout:** Select between Standard or Lower (for TikToks with captions).
6. **Wait:** The bot will download, design, and render the video, then send it back with an AI-generated viral caption.

### Instagram Stories
*Coming soon...*

---

## 🧪 Testing

### Running the Overlay Test (Video Creator)
```bash
python projects/video_creator/tests/test_overlay.py
```
This will generate an `overlay.png` file in the project's temp directory.

---

## 🛠️ Project Structure

```text
parties247-automations/
├── projects/
│   ├── video_creator/          # Video creation bot
│   │   ├── src/
│   │   │   ├── main.py         # Bot entry point & conversation logic
│   │   │   ├── config.py       # Paths and settings
│   │   │   ├── assets/         # Branding images & fonts
│   │   │   └── services/
│   │   │       ├── ai_generator.py # Gemini AI caption logic
│   │   │       ├── downloader.py   # Stealth Playwright/yt-dlp logic
│   │   │       ├── graphics.py     # MoviePy rendering engine
│   │   │       └── text_utils.py   # Hebrew RTL handling
│   │   ├── tests/
│   │   └── requirements.txt
│   │
│   └── instagram_stories/      # Instagram story automation
│       ├── src/
│       │   └── main.py
│       ├── tests/
│       └── requirements.txt
│
├── run_all.py                  # Main orchestrator - runs all projects
├── Dockerfile                  # Unified container configuration
├── requirements.txt            # Combined Python dependencies
└── README.md
```

---

## 📦 Core Dependencies

| Dependency | Purpose |
|------------|---------|
| `moviepy` | Video editing & compositing |
| `google-generativeai` | Gemini 1.5 Flash integration |
| `playwright` | Headless browser automation |
| `python-telegram-bot` | Interactive CLI/Chat interface |
| `Pillow` & `pilmoji` | High-quality image processing with emoji support |
| `instagrapi` | Instagram API client |

---

## 🆕 Adding a New Project

1. Create directory: `projects/<project_name>/`
2. Add subdirectories: `src/`, `tests/`
3. Create `main.py` with an async `main()` function
4. Add project-specific `requirements.txt`
5. Register in `run_all.py` PROJECTS list
6. Add dependencies to root `requirements.txt`