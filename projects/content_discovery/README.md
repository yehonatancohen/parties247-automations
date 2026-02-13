# Content Discovery Bot (TikTok & Instagram Trend Hunter)

A robust automation for discovering potential viral content on TikTok and Instagram.

## Features
- **Parallel Scanning**: Checks up to 5 user accounts simultaneously for speed.
- **Robust Fetching**: Uses `yt-dlp` with advanced retry logic for reliable TikTok scraping.
- **Bot Protection Bypass**: Falls back to "Manual Navigation Mode" via `fetch_followings.py` if needed.
- **Dynamic Scoring**: Ranks videos based on engagement ratio vs. baseline performance.
- **Daily Reporting**: Sends top picks to Telegram.

## Setup
1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Configure Environment**:
   - Create a `.env` or `.env.test` file with your credentials (TIKTOK_SESSION_ID, TELEGRAM_TOKEN, etc.).

3. **User List**:
   - The bot reads from `src/data/monitored_accounts.json` first.
   - If that file is missing or empty, it falls back to `../tiktok_trend_hunter/users.txt`.

## Usage
Run the main bot:
```bash
python src/main.py
```

## Troubleshooting
- If fetching fails completely, check your `TIKTOK_SESSION_ID` cookie.
- If getting rate-limited, increase the `REQUEST_DELAY` in `config.py`.
