import os
import sys
import glob
import random

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

from services.graphics import GraphicsEngine
from config import Config

# Import MoviePy for compositing
from moviepy.editor import (
    VideoFileClip, 
    ImageClip, 
    ColorClip, 
    CompositeVideoClip
)

def main():
    print("🎨 Starting Debug Overlay Generator...")
    
    # Ensure directories exist
    Config.ensure_dirs()
    
    # Initialize Engine
    try:
        engine = GraphicsEngine()
    except Exception as e:
        print(f"❌ Error initializing GraphicsEngine: {e}")
        return

    # Sample Text (Hebrew)
    headline = "כותרת בדיקה יפה 😍"
    body = "זהו טקסט בדיקה כדי לראות איך העיצוב נראה. 🤠\nאנחנו בודקים את הפונט, את המיקום, ואת הצלליות.\nשורה נוספת ארוכה מאוד כדי לבדוק את גלישת הטקסט האוטומטית בתוך השלט. ✨"

    print(f"📝 Generating overlay with:\nTitle: {headline}\nBody: {body[:50]}...")

    try:
        # Call the internal method directly to just get the image
        overlay_path = engine._create_overlay(headline, body)
        
        print(f"✅ Overlay generated successfully at: {overlay_path}")

        # --- VIDEO PREVIEW LOGIC ---
        print("\n🎬 Attempting to create video preview...")
        
        # Find mp4 files in temp
        video_files = glob.glob(os.path.join(Config.TEMP_DIR, "*.mp4"))
        if not video_files:
            print("⚠️ No .mp4 files found in 'temp/' folder. Opening overlay only.")
            final_preview_path = overlay_path
        else:
            # Pick the most recent video
            video_path = max(video_files, key=os.path.getctime)
            print(f"   - Using video: {os.path.basename(video_path)}")
            
            try:
                # Load video and take a frame from the middle
                with VideoFileClip(video_path) as clip:
                    # Duration for the static preview clip
                    preview_duration = 0.1
                    t_frame = min(2.0, clip.duration / 2) # Grab frame at 2s or middle
                    
                    # Create a short clip of just that frame
                    static_clip = clip.subclip(t_frame, t_frame + preview_duration)
                    
                    # --- REPLICATE RENDER LAYOUT LOGIC ---
                    # 1. Background (Black)
                    bg_clip = ColorClip(size=Config.VIDEO_SIZE, color=(0, 0, 0)).set_duration(preview_duration)
                    
                    # 2. Main Content
                    main_clip = static_clip.resize(width=Config.VIDEO_SIZE[0])
                    # Match graphics.py logic: Crop top 180px
                    main_clip = main_clip.crop(y1=180)
                    
                    target_center_y = 1150
                    top_pos = target_center_y - (main_clip.h / 2)
                    main_clip = main_clip.set_position(("center", top_pos))
                    
                    # 3. Top Gap Filler
                    banner_y = 300 
                    top_clip = static_clip.resize(width=Config.VIDEO_SIZE[0])
                    if top_clip.h < banner_y:
                        top_clip = static_clip.resize(height=banner_y)
                    
                    top_clip = top_clip.crop(x_center=top_clip.w/2, y_center=top_clip.h/2, width=Config.VIDEO_SIZE[0], height=banner_y)
                    # Apply blur using the engine's method
                    top_clip = top_clip.fl_image(engine._gaussian_blur)
                    top_clip = top_clip.set_opacity(0.5).set_position(("center", 0))
                    
                    # 4. Overlay
                    overlay_clip = ImageClip(overlay_path).set_duration(preview_duration).set_position("center")
                    
                    # Composite
                    final_comp = CompositeVideoClip([bg_clip, main_clip, top_clip, overlay_clip], size=Config.VIDEO_SIZE)
                    
                    # Save a single frame
                    final_preview_path = os.path.join(Config.TEMP_DIR, "debug_preview.png")
                    print(f"   - Saving preview frame to {final_preview_path}...")
                    final_comp.save_frame(final_preview_path, t=0)
                    print("✅ Video preview created.")
                    
            except Exception as ve:
                print(f"❌ Error creating video preview: {ve}")
                final_preview_path = overlay_path # Fallback
        
        # Try to open the image automatically
        if os.name == 'nt':  # Windows
            os.startfile(final_preview_path)
        elif os.name == 'posix':  # macOS/Linux
            # Try generic opener
            import subprocess
            try:
                subprocess.call(('open', final_preview_path))
            except:
                subprocess.call(('xdg-open', final_preview_path))
                
    except Exception as e:
        print(f"❌ Error generating overlay: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
