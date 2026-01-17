import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from auto_content.services.graphics import GraphicsEngine
from auto_content.config import Config

async def main():
    # Ensure output directories exist
    Config.ensure_dirs()

    # Initialize the graphics engine
    graphics_engine = GraphicsEngine()

    # Define parameters for the video rendering
    video_path = "auto_content/test_video.mp4"
    headline = "This is a test headline"
    body_text = "This is a test body"
    layout_mode = "standard"

    # Render the video
    final_video_path = await asyncio.to_thread(
        graphics_engine.render_video,
        video_path,
        headline,
        body_text,
        layout_mode
    )

    print(f"Video rendering complete. Output file: {final_video_path}")

if __name__ == "__main__":
    asyncio.run(main())