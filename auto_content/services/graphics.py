import os
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np
from moviepy.editor import (
    ImageClip, 
    CompositeVideoClip,
    vfx,
    VideoFileClip,
    ColorClip
)
from config import Config
from services.text_utils import TextUtils
try:
    from pilmoji import Pilmoji
    from pilmoji.source import AppleEmojiSource
    PILMOJI_AVAILABLE = True
except ImportError:
    PILMOJI_AVAILABLE = False
    print("Warning: pilmoji not installed. Emojis may not render correctly.")

class GraphicsEngine:
    def __init__(self):
        self._load_assets()

    def _load_assets(self):
        self.wood_img = Image.open(Config.WOOD_IMAGE_PATH).convert("RGBA")
        
        # Resize wood sign to be slightly wider than screen (110%)
        target_width = int(Config.VIDEO_SIZE[0] * 1.1)
        aspect_ratio = self.wood_img.height / self.wood_img.width
        new_height = int(target_width * aspect_ratio)
        
        self.wood_img = self.wood_img.resize((target_width, new_height), Image.Resampling.LANCZOS)
        
        try:
            self.title_font = ImageFont.truetype(Config.FONT_BOLD, 95) # Increased font size slightly
            self.body_font = ImageFont.truetype(Config.FONT_REGULAR, 60)
        except OSError:
            raise FileNotFoundError("Fonts not found. Check config paths.")

    def _create_overlay(self, headline: str, body: str) -> str:
        print("      > _create_overlay started")
        # Create transparent canvas
        canvas = Image.new('RGBA', Config.VIDEO_SIZE, (0, 0, 0, 0))
        
        # Separate layers for Title and Body to allow different shadow treatments
        title_layer = Image.new('RGBA', Config.VIDEO_SIZE, (0, 0, 0, 0))
        body_layer = Image.new('RGBA', Config.VIDEO_SIZE, (0, 0, 0, 0))
        
        # Initialize Pilmoji managers
        if PILMOJI_AVAILABLE:
            title_pilmoji = Pilmoji(title_layer, source=AppleEmojiSource)
            body_pilmoji = Pilmoji(body_layer, source=AppleEmojiSource)
        else:
            title_pilmoji = None
            body_pilmoji = None
            
        print("      > Canvas created")
        
        # Place Wood Sign
        sign_x = (Config.VIDEO_SIZE[0] - self.wood_img.width) // 2
        sign_y = 280 
        canvas.paste(self.wood_img, (sign_x, sign_y), self.wood_img)
        print(f"      > Wood sign pasted (size: {self.wood_img.size})")
        
        # Text Bounds Calculation
        safe_width = int(Config.VIDEO_SIZE[0] * 0.85) 
        center_x = Config.VIDEO_SIZE[0] // 2
        
        # --- HEADLINE PREP ---
        print("      > Processing Hebrew headline...")
        title_font = self.title_font
        headline_processed = TextUtils.process_hebrew(headline)
        
        while title_font.getlength(headline_processed) > safe_width and title_font.size > 40:
            title_font = ImageFont.truetype(Config.FONT_BOLD, title_font.size - 5)
            
        headline_pos = (center_x, sign_y + 80) 
        
        # --- BODY PREP ---
        print("      > Processing Hebrew body...")
        def wrap_text_by_width(text, font, max_width):
            lines = []
            words = text.split()
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                reshaped_test = TextUtils.process_hebrew(test_line)
                if font.getlength(reshaped_test) <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
                        current_line = []
            if current_line:
                lines.append(' '.join(current_line))
            return lines

        body_start_y = sign_y + 145 
        sign_bottom_y = sign_y + self.wood_img.height
        max_body_y = sign_bottom_y - 65 
        max_available_height = max_body_y - body_start_y
        
        current_body_size = 60
        min_body_size = 25
        final_body_font = None
        final_body_lines = []
        
        while current_body_size >= min_body_size:
            temp_font = ImageFont.truetype(Config.FONT_REGULAR, current_body_size)
            lines = wrap_text_by_width(body, temp_font, safe_width)
            ascent, descent = temp_font.getmetrics()
            line_height = ascent + descent + 4 
            total_height = len(lines) * line_height
            if total_height <= max_available_height:
                final_body_font = temp_font
                final_body_lines = lines
                break
            current_body_size -= 2
            
        if final_body_font is None:
            final_body_font = ImageFont.truetype(Config.FONT_REGULAR, min_body_size)
            final_body_lines = wrap_text_by_width(body, final_body_font, safe_width)

        # --- DRAWING ---

        # Helper to draw centered text
        def draw_centered(manager, layer, position, text, font, fill, stroke_width, stroke_fill):
            if PILMOJI_AVAILABLE and manager:
                try:
                    w, h = manager.getsize(text, font=font)
                    start_x = position[0] - (w // 2)
                    start_y = position[1] - (h // 2)
                    manager.text((start_x, start_y), text, font=font, fill=fill, 
                                 stroke_width=stroke_width, stroke_fill=stroke_fill)
                except Exception:
                    d = ImageDraw.Draw(layer)
                    d.text(position, text, font=font, fill=fill, anchor="mm", 
                           stroke_width=stroke_width, stroke_fill=stroke_fill)
            else:
                d = ImageDraw.Draw(layer)
                d.text(position, text, font=font, fill=fill, anchor="mm", 
                       stroke_width=stroke_width, stroke_fill=stroke_fill)

        # 1. Draw Title to Title Layer (White + Stroke)
        draw_centered(title_pilmoji, title_layer, headline_pos, headline_processed, title_font, "white", 3, "black")
        
        # 2. Draw Body to Body Layer (White + Stroke)
        current_y = body_start_y
        ascent, descent = final_body_font.getmetrics()
        line_height = ascent + descent + 4
        for line in final_body_lines:
             processed_line = TextUtils.process_hebrew(line)
             line_center_y = int(current_y + line_height/2)
             pos = (center_x, line_center_y)
             draw_centered(body_pilmoji, body_layer, pos, processed_line, final_body_font, "#f0f0f0", 2, "black")
             current_y += line_height

        # --- SHADOW GENERATION ---
        
        # Helper to make shadow from layer
        def make_shadow(layer, blur_radius):
            if layer.getbbox():
                alpha = layer.split()[3]
                shadow = Image.new("RGBA", Config.VIDEO_SIZE, (0, 0, 0, 0))
                shadow.paste((0, 0, 0, 255), (0, 0), mask=alpha)
                return shadow.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            return None

        # Title Shadow (Heavy, Multi-offset)
        title_shadow = make_shadow(title_layer, blur_radius=2)
        if title_shadow:
            canvas.paste(title_shadow, (4, 4), title_shadow)
            canvas.paste(title_shadow, (8, 8), title_shadow) # Double paste for depth

        # Body Shadow (Light, Minimal offset)
        body_shadow = make_shadow(body_layer, blur_radius=2)
        if body_shadow:
            # Minimal offset to avoid "duplicate" look on emojis
            canvas.paste(body_shadow, (2, 2), body_shadow) 

        # Paste Main Layers
        canvas.paste(title_layer, (0, 0), title_layer)
        canvas.paste(body_layer, (0, 0), body_layer)
        
        print("      > Text drawn")
        
        overlay_path = os.path.join(Config.TEMP_DIR, "overlay.png")
        print(f"      > Saving overlay to {overlay_path}...")
        canvas.save(overlay_path)
        print("      > Overlay saved")
        return overlay_path

    def _gaussian_blur(self, image):
        """Applies strong Gaussian Blur to a frame using PIL"""
        return np.array(Image.fromarray(image).filter(ImageFilter.GaussianBlur(radius=15)))

    def render_video(self, input_path: str, headline: str, body: str, progress_callback=None) -> str:
        print("🎨 Rendering video...")
        try:
            print("   - Creating overlay...")
            overlay_path = self._create_overlay(headline, body)
            
            # Video Processing
            print("   - Loading video clip...")
            with VideoFileClip(input_path) as clip:
                # Background (Solid Black)
                print("   - Creating background...")
                bg_clip = ColorClip(size=Config.VIDEO_SIZE, color=(0, 0, 0)).set_duration(clip.duration)
                
                # Main Content
                print("   - Processing main content...")
                
                # Resize to always fill width (fit the screen horizontally)
                main_clip = clip.resize(width=Config.VIDEO_SIZE[0])
                
                # Cut the top part (where text usually is)
                # 180px is a safe bet for TikTok/Reels UI/Header
                main_clip = main_clip.crop(y1=180)
                
                # Position the CENTER of the video in the CENTER of the lower part
                # Lower part roughly Y=700 to Y=1920. Center ~1310.
                target_center_y = 1200
                top_pos = target_center_y - (main_clip.h / 2)
                
                main_clip = main_clip.set_position(("center", top_pos))

                # Top Gap Filler (Gap between top of screen and banner)
                print("   - Processing top gap filler...")
                # Banner starts at 280. We extend down to 300 for overlap.
                banner_y = 300 
                
                # Resize to fill width, then crop height
                top_clip = clip.resize(width=Config.VIDEO_SIZE[0])
                # Ensure it's tall enough
                if top_clip.h < banner_y:
                    top_clip = clip.resize(height=banner_y)
                    
                top_clip = top_clip.crop(x_center=top_clip.w/2, y_center=top_clip.h/2, width=Config.VIDEO_SIZE[0], height=banner_y)
                
                # Apply Gaussian Blur (Clean)
                top_clip = top_clip.fl_image(self._gaussian_blur)
                
                # Lower Opacity and Position (0.5 makes it darker against black bg)
                top_clip = top_clip.set_opacity(0.5).set_position(("center", 0))
                
                # Overlay
                print("   - Adding overlay...")
                overlay_clip = ImageClip(overlay_path).set_duration(clip.duration).set_position("center")
                
                # Composite
                print("   - Compositing final video...")
                # Layer order: 
                # 1. Background (Black)
                # 2. Main Clip (might overflow up)
                # 3. Top Clip (covers the overflow at the top 0-300)
                # 4. Banner (overlay)
                final = CompositeVideoClip([bg_clip, main_clip, top_clip, overlay_clip], size=Config.VIDEO_SIZE)
                final = final.set_duration(clip.duration) # Ensure duration matches
                
                output_path = os.path.join(Config.OUTPUT_DIR, f"final_{os.path.basename(input_path)}")
                
                # Write file
                print(f"   - Writing video file to {output_path}...")
                final.write_videofile(
                    output_path, 
                    codec='libx264', 
                    fps=24, 
                    preset='ultrafast',  # Faster rendering for testing
                    threads=4,
                    logger=None
                )
                
            return output_path
        except Exception as e:
            print(f"Error in render_video: {e}")
            raise e