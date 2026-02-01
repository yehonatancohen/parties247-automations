import os
import sys
import subprocess
import shutil
import imageio_ffmpeg

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.graphics import GraphicsEngine
from config import Config

def run_visual_test():
    Config.ensure_dirs()
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # Input video
    input_video = os.path.join(Config.TEMP_DIR, "dummy_video.mp4")
    if not os.path.exists(input_video):
        print(f"Error: Input video not found at {input_video}")
        return

    graphics = GraphicsEngine()
    
    headline = "כותרת בדיקה 🍎" 
    body = "זוהי בדיקה עם אימוג'י בסוף שורה 🚀\nשורות נוספות כאן."
    
    modes = ['lower', 'full']
    
    for mode in modes:
        print(f"\n--- Testing Layout Mode: {mode} ---")
        try:
            # Render
            output_path = graphics.render_video(input_video, headline, body, layout_mode=mode)
            print(f"Video rendered to: {output_path}")
            
            # Since render_video overwrites the same file for the same input, 
            # we should rename it or process it immediately.
            # We'll rename it to keep it.
            base_name = os.path.basename(output_path)
            mode_output_path = os.path.join(os.path.dirname(output_path), f"{mode}_{base_name}")
            shutil.move(output_path, mode_output_path)
            print(f"Moved to: {mode_output_path}")
            
            # Take a screenshot at 00:00:02
            screenshot_path = os.path.join(os.path.dirname(__file__), f"test_result_{mode}.jpg")
            
            cmd = [
                ffmpeg_exe,
                '-y',
                '-ss', '00:00:02',
                '-i', mode_output_path,
                '-vframes', '1',
                '-q:v', '2',
                screenshot_path
            ]
            
            print(f"Extracting screenshot for {mode}...")
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"Screenshot saved to: {screenshot_path}")
            
        except Exception as e:
            print(f"An error occurred in mode {mode}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    run_visual_test()
