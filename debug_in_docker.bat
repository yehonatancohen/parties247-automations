@echo off
echo 🚀 Running Debug Overlay in Docker (with Volume Mount)...
echo.
echo NOTE: This uses the 'parties-bot' image. Make sure you built it at least once!
echo (docker build -t parties-bot .)
echo.

docker run -it --rm -v "%cd%:/app" parties-bot python auto_content/debug_overlay.py

echo.
echo ✅ Done! Check 'auto_content/temp/overlay.png' to see the result.
pause
