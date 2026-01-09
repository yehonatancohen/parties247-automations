import os
import sys

# Add parent dir to path to find other modules if needed, but config is local here
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from PIL import ImageFont

print(f"CWD: {os.getcwd()}")
print(f"Config.FONT_BOLD: {Config.FONT_BOLD}")
print(f"Exists: {os.path.exists(Config.FONT_BOLD)}")

try:
    font = ImageFont.truetype(Config.FONT_BOLD, 95)
    print("Font loaded successfully.")
except OSError as e:
    print(f"Error loading font: {e}")
