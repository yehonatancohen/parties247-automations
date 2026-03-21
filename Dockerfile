# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production

# Load and set required environment variables from args during build
ARG TELEGRAM_TOKEN
ENV TELEGRAM_TOKEN=$TELEGRAM_TOKEN

ARG ALLOWED_USER_ID
ENV ALLOWED_USER_ID=$ALLOWED_USER_ID

ARG GEMINI_API_KEY
ENV GEMINI_API_KEY=$GEMINI_API_KEY

ARG FONT_PATH=/usr/share/fonts/truetype/custom/Rubik-ExtraBold.ttf
ENV FONT_PATH=$FONT_PATH

ARG TIKTOK_USERNAME
ENV TIKTOK_USERNAME=$TIKTOK_USERNAME

ARG TIKTOK_PASSWORD
ENV TIKTOK_PASSWORD=$TIKTOK_PASSWORD

ARG INSTAGRAM_CD_USERNAME
ENV INSTAGRAM_CD_USERNAME=$INSTAGRAM_CD_USERNAME

ARG INSTAGRAM_CD_PASSWORD
ENV INSTAGRAM_CD_PASSWORD=$INSTAGRAM_CD_PASSWORD

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    git \
    curl \
    libfreetype6-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    fontconfig \
    tesseract-ocr \
    tesseract-ocr-heb \
    && rm -rf /var/lib/apt/lists/*

# Copy local fonts to system font directory
RUN mkdir -p /usr/share/fonts/truetype/custom
COPY projects/video_creator/src/assets/fonts/ /usr/share/fonts/truetype/custom/

# Refresh font cache
RUN fc-cache -f -v

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install content discovery specific dependencies
RUN pip install --no-cache-dir instagrapi aiohttp feedparser beautifulsoup4 lxml

# Install Playwright browsers and their system dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy project files
COPY projects/ projects/
COPY run_all.py .

# Ensure necessary directories exist for each project
RUN mkdir -p projects/video_creator/src/temp projects/video_creator/src/output
RUN mkdir -p projects/instagram_stories/src/temp projects/instagram_stories/src/output
RUN mkdir -p projects/content_discovery/src/data projects/content_discovery/src/sessions

# Run all automation projects
CMD ["python", "run_all.py"]