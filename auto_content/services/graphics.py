import os
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, features
import numpy as np

# Monkey patch ANTIALIAS for older libraries (moviepy, pilmoji)
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# Check for Raqm support (essential for correct Emoji + Hebrew mixing)
try:
    RAQM_SUPPORT = features.check("raqm")
except Exception:
    RAQM_SUPPORT = False

from moviepy.editor import (
    ImageClip,
    CompositeVideoClip,
    vfx,
    VideoFileClip,
    ColorClip
)
from ..config import Config
from .text_utils import TextUtils

try:
    from pilmoji import Pilmoji
    from pilmoji.source import AppleEmojiSource, MicrosoftEmojiSource, TwitterEmojiSource
    PILMOJI_AVAILABLE = True
except ImportError:
    PILMOJI_AVAILABLE = False
    print("Warning: pilmoji not installed. Emojis may not render correctly.")

class GraphicsEngine:
    def __init__(self):
        try:
            print(f"🔍 PIL Raqm support: {RAQM_SUPPORT}")
        except Exception as e:
            print(f"⚠️ Could not check PIL features: {e}")

        # --- TEXT POSITIONING CONFIG ---
        # Adjust these based on your ready-made overlay image
        self.text_start_y = 330   
        self.sign_height = 400    
        
        self._load_assets()

    def _load_assets(self):
        # 1. Load the Single Ready-Made Overlay
        overlay_path = getattr(Config, "READY_OVERLAY_PATH", os.path.join(Config.ASSETS_DIR, "overlay_template.png"))
        
        print(f"🌲 Loading ready overlay from: {overlay_path}")
        if not os.path.exists(overlay_path):
             print(f"⚠️ Overlay template not found at {overlay_path}. Using fallback wood sign logic.")
             overlay_path = Config.WOOD_IMAGE_PATH
        
        self.overlay_base = Image.open(overlay_path).convert("RGBA")
        
        # Resize overlay to fit video width exactly (assuming 1080px width standard)
        target_width = Config.VIDEO_SIZE[0]
        if self.overlay_base.width != target_width:
            aspect_ratio = self.overlay_base.height / self.overlay_base.width
            new_height = int(target_width * aspect_ratio)
            self.overlay_base = self.overlay_base.resize((target_width, new_height), Image.Resampling.LANCZOS)
            
        # Store height for layout calculations
        self.overlay_height = self.overlay_base.height

        # Load Fonts
        try:
            print(f"Loading font from: {Config.FONT_BOLD}")
            # FIX: Removed layout_engine=ImageFont.Layout.BASIC
            # We let Pillow/Raqm handle the layout so Emojis don't break.
            self.title_font = ImageFont.truetype(Config.FONT_BOLD, 95) 
            self.body_font = ImageFont.truetype(Config.FONT_REGULAR, 60)
        except OSError as e:
            print(f"OSError loading font: {e}")
            raise FileNotFoundError(f"Fonts not found or invalid. Error: {e}")

    def _create_overlay(self, headline: str, body: str) -> str:
        # Start with the ready-made overlay as the canvas
        canvas = self.overlay_base.copy()
        
        # Separate layers for Text (to allow independent shadow/processing if needed)
        text_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        
        # Initialize Pilmoji
        if PILMOJI_AVAILABLE:
            # Using AppleEmojiSource for the requested "iPhone" look
            text_pilmoji = Pilmoji(text_layer, source=AppleEmojiSource)
        else:
            text_pilmoji = None
            
        # Positioning Logic
        center_x = canvas.width // 2
        safe_width = int(canvas.width * 0.85)
        
        # Anchor point (Top of the "sign" area)
        sign_y = self.text_start_y
        
        # --- HEADLINE PREP ---
        title_font = self.title_font
        
        # FIX: Only process Hebrew manually if Raqm (advanced layout) is missing.
        # Manual processing breaks multi-character emojis (like rain cloud).
        if RAQM_SUPPORT:
            headline_processed = headline
        else:
            headline_processed = TextUtils.process_hebrew(headline)
        
        # Dynamic font scaling
        while title_font.getlength(headline_processed) > safe_width and title_font.size > 40:
            title_font = ImageFont.truetype(Config.FONT_BOLD, title_font.size - 5)
            
        headline_pos = (center_x, sign_y + 75) 
        
        # --- BODY PREP ---
        def wrap_paragraph(text, font, max_width):
            lines = []
            words = text.split()
            current_line = []
            for word in words:
                # Build test line
                test_line_words = current_line + [word]
                raw_test_line = ' '.join(test_line_words)
                
                # Check width: use raw line if Raqm is supported, else process Hebrew first
                if RAQM_SUPPORT:
                    test_line_visual = raw_test_line
                else:
                    test_line_visual = TextUtils.process_hebrew(raw_test_line)
                
                if font.getlength(test_line_visual) <= max_width:
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

        def process_body_text(body_text, font, max_width):
            paragraphs = body_text.split('\n')
            final_lines = []
            for p in paragraphs:
                if not p.strip():
                    final_lines.append("") 
                    continue
                wrapped = wrap_paragraph(p, font, max_width)
                final_lines.extend(wrapped)
            return final_lines

        # Calculate Text Area Boundaries
        body_start_y = sign_y + 140
        max_body_y = sign_y + self.sign_height - 45 
        max_available_height = max_body_y - body_start_y
        
        current_body_size = 90
        min_body_size = 25
        final_body_font = None
        final_body_lines = []
        
        # Fit body text to available height
        while current_body_size >= min_body_size:
            temp_font = ImageFont.truetype(Config.FONT_REGULAR, current_body_size)
            lines = process_body_text(body, temp_font, safe_width)
            
            ascent, descent = temp_font.getmetrics()
            line_height = ascent + descent + 4 
            total_height = len(lines) * line_height
            
            # If height fits OR we are at min size (force fit)
            if total_height <= max_available_height or current_body_size == min_body_size:
                final_body_font = temp_font
                final_body_lines = lines
                break
            current_body_size -= 2
            
        if final_body_font is None:
            final_body_font = ImageFont.truetype(Config.FONT_REGULAR, min_body_size)
            final_body_lines = process_body_text(body, final_body_font, safe_width)

        # --- DRAWING ---
        def draw_centered(manager, layer, position, text, font, fill, stroke_width, stroke_fill):
            if PILMOJI_AVAILABLE and manager:
                try:
                    w, h = manager.getsize(text, font=font)
                    start_x = position[0] - (w // 2)
                    start_y = position[1] - (h // 2) + 5 
                    manager.text((start_x, start_y), text, font=font, fill=fill, 
                                 stroke_width=stroke_width, stroke_fill=stroke_fill)
                except Exception as e:
                    print(f"⚠️ Pilmoji (Apple) render failed for '{text}': {e}. Trying fallback to Twitter Source.")
                    try:
                         # Fallback to Twitter Source on failure
                         with Pilmoji(layer, source=TwitterEmojiSource) as fallback_pilmoji:
                            w, h = fallback_pilmoji.getsize(text, font=font)
                            start_x = position[0] - (w // 2)
                            start_y = position[1] - (h // 2) + 5
                            fallback_pilmoji.text((start_x, start_y), text, font=font, fill=fill, 
                                            stroke_width=stroke_width, stroke_fill=stroke_fill)
                    except Exception as e2:
                        print(f"❌ Fallback Pilmoji failed: {e2}. Using basic text.")
                        d = ImageDraw.Draw(layer)
                        d.text(position, text, font=font, fill=fill, anchor="mm", 
                            stroke_width=stroke_width, stroke_fill=stroke_fill)
            else:
                d = ImageDraw.Draw(layer)
                d.text(position, text, font=font, fill=fill, anchor="mm", 
                       stroke_width=stroke_width, stroke_fill=stroke_fill)

        # 1. Draw Headline
        draw_centered(text_pilmoji, text_layer, headline_pos, headline_processed, title_font, "white", 3, "black")
        
        # 2. Draw Body
        current_y = body_start_y
        ascent, descent = final_body_font.getmetrics()
        line_height = ascent + descent + 4
        
        for line in final_body_lines:
             # FIX: Same conditional logic for body text drawing
             if RAQM_SUPPORT:
                 processed_line = line
             else:
                 processed_line = TextUtils.process_hebrew(line)
             
             line_center_y = int(current_y + line_height/2)
             pos = (center_x, line_center_y)
             draw_centered(text_pilmoji, text_layer, pos, processed_line, final_body_font, "#f0f0f0", 3, "black")
             current_y += line_height

        # --- SHADOWS ---
        def make_shadow(layer, blur_radius):
            if layer.getbbox():
                alpha = layer.split()[3]
                shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                shadow.paste((0, 0, 0, 255), (0, 0), mask=alpha)
                return shadow.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            return None

        # Create text shadow
        text_shadow = make_shadow(text_layer, blur_radius=3)
        
        # Paste Order: Canvas (Overlay) -> Shadow -> Text
        if text_shadow:
            canvas.paste(text_shadow, (3, 3), text_shadow)
            
        canvas.paste(text_layer, (0, 0), text_layer)
        
        overlay_path = os.path.join(Config.TEMP_DIR, "overlay.png")
        canvas.save(overlay_path)
        return overlay_path

    def render_video(self, input_path: str, headline: str, body: str, layout_mode: str = 'lower', progress_callback=None) -> str:
        """
        Renders the final video using a raw ffmpeg command.
        """
        import subprocess

        print(f"🎨 Rendering video ({layout_mode})...")
        
        overlay_path = self._create_overlay(headline, body)
        
        base_name = os.path.basename(input_path)
        output_filename = f"final_{base_name}"
        output_path = os.path.join(Config.OUTPUT_DIR, output_filename)

        ffmpeg_cmd = [
            'ffmpeg',
            '-i', input_path,
            '-i', overlay_path,
            '-filter_complex',
            "[0:v]setpts=PTS/1.05,crop=in_w*0.96:in_h*0.96,scale=1080:1920,eq=gamma=1.05,noise=alls=1:allf=t[v];" +
            "[0:a]atempo=1.05[a];" +
            "[v][1:v]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[out]",
            '-map', '[out]',
            '-map', '[a]',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'medium',
            '-b:v', '2500k',
            '-y', # Overwrite output file if it exists
            '-map_metadata', '-1',
            output_path
        ]

        try:
            print(f"💾 Saving video to: {output_path}")
            subprocess.run(ffmpeg_cmd, check=True)
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"Error in render_video: {e}")
            raise e