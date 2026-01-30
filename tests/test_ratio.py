"""
Test script to verify the proportional spacing of text on the overlay banner.
This creates an overlay and saves it for visual inspection.
"""
import os
import sys
from PIL import Image, ImageDraw

os.environ['ALLOWED_USER_ID'] = '12345'  # Dummy value for testing

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))

from services.graphics import GraphicsEngine
from config import Config


def test_proportional_spacing():
    """
    Tests the proportional spacing by creating an overlay and annotating it
    with measurement lines to visualize the spacing.
    """
    Config.ensure_dirs()
    
    # Test with long single-line text (let the code break lines automatically)
    test_cases = [
        ("כותרת קצרה", "טקסט גוף קצר מאוד"),
        ("מסיבת יום הולדת", "הצטרפו אלינו לחגיגה הכי גדולה של השנה! המון הפתעות אטרקציות ובילויים מטורפים מחכים לכם. מקום: האולם הגדול בתל אביב. תאריך: יום שישי בשעה 20:00. כניסה חופשית לכל המשפחה!"),
        ("🎉 מסיבה!", "בואו לחגוג איתנו את האירוע הכי שווה! 🎂 נהיה שם עם אוכל מעולה משקאות קרים ומוזיקה שתרים אתכם מהכיסאות. אל תפספסו את ההזדמנות הזאת! 💃🕺"),
    ]
    
    graphics_engine = GraphicsEngine()
    
    # Get spacing parameters
    sign_y = graphics_engine.text_start_y
    sign_height = graphics_engine.sign_height
    sign_bottom = sign_y + sign_height
    
    top_padding = int(sign_height * 0.12)
    title_area_height = int(sign_height * 0.18)
    gap_after_title = int(sign_height * 0.10)
    bottom_padding = int(sign_height * 0.18)
    body_area_start = top_padding + title_area_height + gap_after_title
    
    title_center_y = sign_y + top_padding + (title_area_height // 2)
    body_start_y = sign_y + body_area_start
    body_end_y = sign_bottom - bottom_padding
    
    # Print measurements
    print("\n" + "=" * 60)
    print("PROPORTIONAL SPACING MEASUREMENTS")
    print("=" * 60)
    print(f"Sign area: Y={sign_y} to Y={sign_bottom} (height={sign_height}px)")
    print("-" * 60)
    print(f"Top padding:     {top_padding}px  (12% of {sign_height})")
    print(f"Title area:      {title_area_height}px  (18% of {sign_height})")
    print(f"Gap after title: {gap_after_title}px  (10% of {sign_height})")
    print(f"Body area:       {body_end_y - body_start_y}px  (~42% of {sign_height})")
    print(f"Bottom padding:  {bottom_padding}px  (18% of {sign_height})")
    print("-" * 60)
    print(f"Title center at: Y={title_center_y} (relative: {title_center_y - sign_y}px from sign top)")
    print(f"Body starts at:  Y={body_start_y} (relative: {body_start_y - sign_y}px from sign top)")
    print(f"Body ends at:    Y={body_end_y} (relative: {body_end_y - sign_y}px from sign top)")
    print("=" * 60 + "\n")
    
    # Create overlays for each test case
    for i, (headline, body) in enumerate(test_cases):
        print(f"Creating overlay {i+1}: '{headline[:20].encode('utf-8', errors='replace').decode('utf-8')}...'")
        
        # Create the overlay
        overlay_path = graphics_engine._create_overlay(headline, body)
        
        # Open and annotate with measurement lines
        img = Image.open(overlay_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # Draw measurement lines (red = boundaries, green = text areas)
        line_color_boundary = (255, 0, 0)  # Red for sign boundaries
        line_color_zones = (0, 255, 0)  # Green for text zones
        
        # Sign top and bottom boundaries
        draw.line([(0, sign_y), (img.width, sign_y)], fill=line_color_boundary, width=2)
        draw.line([(0, sign_bottom), (img.width, sign_bottom)], fill=line_color_boundary, width=2)
        
        # Padding zones
        draw.line([(0, sign_y + top_padding), (img.width, sign_y + top_padding)], fill=line_color_zones, width=1)
        draw.line([(0, sign_bottom - bottom_padding), (img.width, sign_bottom - bottom_padding)], fill=line_color_zones, width=1)
        
        # Title center line (blue)
        draw.line([(0, title_center_y), (img.width, title_center_y)], fill=(0, 0, 255), width=1)
        
        # Body start line (yellow)
        draw.line([(0, body_start_y), (img.width, body_start_y)], fill=(255, 255, 0), width=1)
        
        # Save annotated version
        test_output_path = os.path.join(os.path.dirname(__file__), f"test_ratio_result_{i+1}.jpg")
        img.save(test_output_path, quality=90)
        print(f"  ✅ Saved annotated overlay to: {test_output_path}")
    
    # Create clean version without lines for final check
    clean_overlay_path = graphics_engine._create_overlay(
        "🎉 מסיבת יום הולדת!",
        "הצטרפו אלינו לחגיגה\nמקום: האולם הגדול\nתאריך: יום שישי 20:00\nכניסה חופשית! 🎂"
    )
    
    # Copy to test folder
    clean_img = Image.open(clean_overlay_path)
    clean_output_path = os.path.join(os.path.dirname(__file__), "test_ratio_clean.jpg")
    clean_img.convert("RGB").save(clean_output_path, quality=95)
    print(f"\n✅ Clean overlay (no lines) saved to: {clean_output_path}")
    
    print("\n✅ All ratio tests completed successfully!")
    print("Check the generated images in the tests folder to verify proportions visually.")
    
    return True


if __name__ == "__main__":
    test_proportional_spacing()
