# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for MoviePy, Playwright, and Pillow (Font/Raqm support)
# Removed libfribidi/libharfbuzz to disable Raqm and force Basic text rendering (fixes Hebrew reversal issues)
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
    && rm -rf /var/lib/apt/lists/*

# Copy local fonts to system font directory
RUN mkdir -p /usr/share/fonts/truetype/custom
COPY auto_content/assets/fonts/ /usr/share/fonts/truetype/custom/

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
COPY . .

# Ensure necessary directories exist
RUN mkdir -p auto_content/temp auto_content/output

# Run the bot
CMD ["python", "auto_content/main.py"]
