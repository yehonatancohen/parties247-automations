import os
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, features
import numpy as np

# Monkey patch ANTIALIAS for older libraries (moviepy, pilmoji)
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

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
            # Force BASIC layout engine to bypass Raqm (fixes Hebrew double-reversal on Docker)
            # Using ImageFont.Layout.BASIC (Enum) for Pillow 10+
            self.title_font = ImageFont.truetype(Config.FONT_BOLD, 95, layout_engine=ImageFont.Layout.BASIC) 
            self.body_font = ImageFont.truetype(Config.FONT_REGULAR, 60, layout_engine=ImageFont.Layout.BASIC)
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
        headline_processed = TextUtils.process_hebrew(headline)
        
        # Dynamic font scaling
        while title_font.getlength(headline_processed) > safe_width and title_font.size > 40:
            title_font = ImageFont.truetype(Config.FONT_BOLD, title_font.size - 5, layout_engine=ImageFont.Layout.BASIC)
            
        headline_pos = (center_x, sign_y + 85) 
        
        # --- BODY PREP ---
        def wrap_paragraph(text, font, max_width):
            lines = []
            words = text.split()
            current_line = []
            for word in words:
                # Build test line (Logical) -> Measure (Visual)
                test_line_words = current_line + [word]
                test_line_visual = TextUtils.process_hebrew(' '.join(test_line_words))
                
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
        # Using previous tuning: start + 155, bottom margin 45
        body_start_y = sign_y + 155
        max_body_y = sign_y + self.sign_height - 45 
        max_available_height = max_body_y - body_start_y
        
        current_body_size = 90
        min_body_size = 25
        final_body_font = None
        final_body_lines = []
        
        # Fit body text to available height
        while current_body_size >= min_body_size:
            temp_font = ImageFont.truetype(Config.FONT_REGULAR, current_body_size, layout_engine=ImageFont.Layout.BASIC)
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
            final_body_font = ImageFont.truetype(Config.FONT_REGULAR, min_body_size, layout_engine=ImageFont.Layout.BASIC)
            final_body_lines = process_body_text(body, final_body_font, safe_width)

        # --- DRAWING ---
        def draw_centered(manager, layer, position, text, font, fill, stroke_width, stroke_fill):
            # We use Basic Layout (forced in font loader), so no special kwargs needed.
            
            if PILMOJI_AVAILABLE and manager:
                try:
                    w, h = manager.getsize(text, font=font)
                    start_x = position[0] - (w // 2)
                    start_y = position[1] - (h // 2) + 5 
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

        # 1. Draw Headline
        draw_centered(text_pilmoji, text_layer, headline_pos, headline_processed, title_font, "white", 3, "black")
        
        # 2. Draw Body
        current_y = body_start_y
        ascent, descent = final_body_font.getmetrics()
        line_height = ascent + descent + 4
        for line in final_body_lines:
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
        Renders the final video.
        Uses scale-blur (downscale/upscale) to fix memory issues.
        """
        print(f"🎨 Rendering video ({layout_mode})...")
        
        def make_even(n):
            n = int(n)
            return n if n % 2 == 0 else n + 1

        try:
            overlay_path = self._create_overlay(headline, body)
            
            with VideoFileClip(input_path) as clip:
                target_w = make_even(Config.VIDEO_SIZE[0])
                target_h = make_even(Config.VIDEO_SIZE[1])
                
                # Base Black Background
                bg_clip = ColorClip(size=(target_w, target_h), color=(0, 0, 0)).set_duration(clip.duration)
                
                # Main Video Content
                main_clip = clip.resize(width=target_w)
                main_clip = main_clip.resize(height=make_even(main_clip.h))
                
                # Layout Logic
                if layout_mode == 'lower':
                    crop_y = 180
                    if main_clip.h > crop_y + 100:
                        main_clip = main_clip.crop(y1=crop_y)
                        main_clip = main_clip.resize(height=make_even(main_clip.h))
                    
                    # Background source for blur
                    bg_source_clip = clip.crop(y1=min(crop_y, clip.h - 10))
                    
                    target_center_y = 1250 
                else:
                    target_center_y = target_h // 2
                    bg_source_clip = clip
                
                # Center Logic with top banner avoidance
                top_pos = int(target_center_y - (main_clip.h / 2))
                banner_safe_y = 620
                if top_pos < banner_safe_y:
                    overlap = banner_safe_y - top_pos
                    if main_clip.h > overlap + 50:
                        main_clip = main_clip.crop(y1=int(overlap))
                        main_clip = main_clip.resize(height=make_even(main_clip.h))
                        top_pos = banner_safe_y

                main_clip = main_clip.set_position(("center", int(top_pos)))

                # --- BACKGROUND VIDEO (DARK & CLEAN) ---
                # Removed the blur to prevent pixelation. 
                # We simply dim the background video against the black base.
                bg_video_clip = bg_source_clip.resize(height=target_h) 
                
                # Crop center to fit screen
                if bg_video_clip.w < target_w:
                    bg_video_clip = bg_video_clip.resize(width=target_w)
                    
                bg_video_clip = bg_video_clip.resize(width=make_even(bg_video_clip.w))
                
                bg_video_clip = bg_video_clip.crop(x_center=bg_video_clip.w//2, y_center=bg_video_clip.h//2, 
                                                   width=target_w, height=target_h)
                
                # Dim the video (Darker look)
                bg_video_clip = bg_video_clip.set_opacity(0.25).set_position("center")
                
                # Overlay
                overlay_clip = ImageClip(overlay_path).set_duration(clip.duration).set_position("center")
                
                # Composite
                final = CompositeVideoClip([bg_clip, bg_video_clip, main_clip, overlay_clip], size=(target_w, target_h))
                final = final.set_duration(clip.duration)
                
                base_name = os.path.basename(input_path)
                output_filename = f"final_{base_name}"
                output_path = os.path.join(Config.OUTPUT_DIR, output_filename)
                
                print(f"💾 Saving video to: {output_path}")
                
                final.write_videofile(
                    output_path, 
                    codec='libx264', 
                    fps=24, 
                    preset='medium',
                    bitrate="2500k",
                    audio_codec="aac",
                    threads=4,
                    logger='bar'
                )
                
            return output_path
        except Exception as e:
            print(f"Error in render_video: {e}")
            raise e
