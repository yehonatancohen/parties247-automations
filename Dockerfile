# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production

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
COPY src/assets/fonts/ /usr/share/fonts/truetype/custom/

# Refresh font cache
RUN fc-cache -f -v

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and their system dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy project files
COPY src/ .
COPY tests/ tests/

# Ensure necessary directories exist
RUN mkdir -p temp output

# Run the bot
CMD ["python", "main.py"]