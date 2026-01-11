import sys
import os
from PIL import features, ImageFont

def check():
    print("--- Environment Check ---")
    print(f"Python: {sys.version}")
    
    # Check Raqm
    has_raqm = features.check('raqm')
    print(f"PIL Raqm Support: {has_raqm}")
    
    # Check if we can force Basic
    try:
        basic = ImageFont.LAYOUT_BASIC
        print(f"ImageFont.LAYOUT_BASIC available: Yes ({basic})")
    except AttributeError:
        print("ImageFont.LAYOUT_BASIC available: No")

    print("-------------------------")

if __name__ == "__main__":
    check()
