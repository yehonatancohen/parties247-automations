import os
import sys

# Ensure we can import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config import Config
except ImportError:
    print("Could not import config.")
    sys.exit(1)
except ValueError as e:
    print(f"Config import failed (likely missing env vars): {e}")
    # Mock Config for path checking
    class Config:
        ASSETS_DIR = "assets"
        FONT_BOLD = os.path.join(ASSETS_DIR, "fonts", "Rubik-Bold.ttf")
        FONT_REGULAR = os.path.join(ASSETS_DIR, "fonts", "Rubik-Bold.ttf") # As per read file

print(f"Current Working Directory: {os.getcwd()}")
print(f"Config.ASSETS_DIR: {Config.ASSETS_DIR}")
print(f"Config.FONT_BOLD: {Config.FONT_BOLD}")

abs_font_path = os.path.abspath(Config.FONT_BOLD)
print(f"Absolute Font Path: {abs_font_path}")

if os.path.exists(Config.FONT_BOLD):
    print("✅ Font file exists.")
    print(f"File size: {os.path.getsize(Config.FONT_BOLD)} bytes")
    
    # Try loading
    from PIL import ImageFont
    try:
        font = ImageFont.truetype(Config.FONT_BOLD, 95)
        print("✅ Font loaded successfully via PIL.")
    except Exception as e:
        print(f"❌ PIL failed to load font: {e}")
else:
    print("❌ Font file NOT found.")
    # List assets dir if it exists
    if os.path.exists(Config.ASSETS_DIR):
        print(f"Contents of {Config.ASSETS_DIR}:")
        for root, dirs, files in os.walk(Config.ASSETS_DIR):
            for file in files:
                print(os.path.join(root, file))
    else:
        print(f"❌ Assets directory '{Config.ASSETS_DIR}' not found.")
