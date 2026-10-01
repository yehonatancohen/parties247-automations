# Video-creator MCP server (headless pipeline). Build context: the repo root.
#   docker build -f projects/video_creator/deploy/Dockerfile -t video-mcp .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fontconfig libraqm0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/projects/video_creator/src

# Only what the headless pipeline imports (no Telegram bot, no Playwright browsers).
# Playwright is still needed as a module: services/downloader.py imports it at load time,
# but its browser fallback is not installed, so it fails gracefully.
RUN pip install --no-cache-dir \
    "mcp<2" "moviepy<2.0.0" Pillow numpy python-bidi arabic-reshaper "emoji<2.0.0" pilmoji==2.0.4 \
    yt-dlp requests python-dotenv google-generativeai imageio-ffmpeg playwright

COPY projects/video_creator/src/ /app/projects/video_creator/src/

RUN mkdir -p output/jobs output/inbox temp
EXPOSE 8765
CMD ["python", "mcp_server.py", "--host", "0.0.0.0", "--port", "8765"]
