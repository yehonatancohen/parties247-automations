import os
from auto_content.config import Config
from PIL import ImageFont

print(f"CWD: {os.getcwd()}")
print(f"Config.FONT_BOLD: {Config.FONT_BOLD}")
print(f"Exists: {os.path.exists(Config.FONT_BOLD)}")

try:
    font = ImageFont.truetype(Config.FONT_BOLD, 95)
    print("Font loaded successfully.")
except OSError as e:
    print(f"Error loading font: {e}")
