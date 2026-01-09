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
        # Load Wood Sign
        self.wood_img = Image.open(Config.WOOD_IMAGE_PATH).convert("RGBA")
        
        # Resize wood sign to be slightly wider than screen (110%)
        target_width = int(Config.VIDEO_SIZE[0] * 1.1)
        aspect_ratio = self.wood_img.height / self.wood_img.width
        new_height = int(target_width * aspect_ratio)
        self.wood_img = self.wood_img.resize((target_width, new_height), Image.Resampling.LANCZOS)
        
        # Load Parties Logo
        logo_path = os.path.join(Config.ASSETS_DIR, "partieslogo_white.png")
        if os.path.exists(logo_path):
            self.logo_img = Image.open(logo_path).convert("RGBA")
            # Resize logo to width 180px (Bigger)
            logo_width = 180
            logo_aspect = self.logo_img.height / self.logo_img.width
            logo_height = int(logo_width * logo_aspect)
            self.logo_img = self.logo_img.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
        else:
            print(f"⚠️ Logo not found at {logo_path}")
            self.logo_img = None
        
        try:
            print(f"Loading font from: {Config.FONT_BOLD}")
            if os.path.exists(Config.FONT_BOLD):
                size = os.path.getsize(Config.FONT_BOLD)
                print(f"Font file size: {size} bytes")
                with open(Config.FONT_BOLD, 'rb') as f:
                    header = f.read(4)
                    print(f"Font header: {header.hex()}")
            
            self.title_font = ImageFont.truetype(Config.FONT_BOLD, 95) 
            self.body_font = ImageFont.truetype(Config.FONT_REGULAR, 60)
        except OSError as e:
            print(f"OSError loading font: {e}")
            raise FileNotFoundError(f"Fonts not found or invalid at {Config.FONT_BOLD}. Error: {e}")

    def _create_overlay(self, headline: str, body: str) -> str:
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
            
        # Place Wood Sign
        sign_x = (Config.VIDEO_SIZE[0] - self.wood_img.width) // 2
        sign_y = 280 
        
        # --- FIX START: Solid Opaque Backing ---
        if self.wood_img.mode == 'RGBA':
            # 1. Get the alpha channel
            r, g, b, alpha = self.wood_img.split()
            
            # 2. THRESHOLD: Force semi-transparent pixels to be 100% Opaque (255).
            # This ensures the middle of the board is a solid wall that blocks video text.
            solid_mask = alpha.point(lambda p: 255 if p > 10 else 0)
            
            # 3. ERODE: Shrink this solid block by 5 pixels (MUST BE ODD).
            # We shrink it so this hard black block hides *inside* the soft wood edges.
            eroded_mask = solid_mask.filter(ImageFilter.MinFilter(5))
            
            # 4. BLUR: Soften the edges of the black block slightly so it blends.
            backing_mask = eroded_mask.filter(ImageFilter.GaussianBlur(1))
            
            # 5. Create the Solid Black Layer
            black_bg = Image.new('RGBA', self.wood_img.size, (0, 0, 0, 255))
            
            # 6. Paste Backing First
            canvas.paste(black_bg, (sign_x, sign_y), mask=backing_mask)
            
        # 7. Paste Wood Image on Top
        canvas.paste(self.wood_img, (sign_x, sign_y), self.wood_img)
        # --- FIX END ---
        
        # Place Logo (Under the banner)
        if self.logo_img:
            center_x = Config.VIDEO_SIZE[0] // 2
            # Position: Closer to banner (sign_y + height - 5)
            logo_y = sign_y + self.wood_img.height - 5 
            logo_x = center_x - (self.logo_img.width // 2)
            canvas.paste(self.logo_img, (logo_x, logo_y), self.logo_img)
        
        # Text Bounds Calculation
        safe_width = int(Config.VIDEO_SIZE[0] * 0.85) 
        center_x = Config.VIDEO_SIZE[0] // 2
        
        # --- HEADLINE PREP ---
        title_font = self.title_font
        headline_processed = TextUtils.process_hebrew(headline)
        
        while title_font.getlength(headline_processed) > safe_width and title_font.size > 40:
            title_font = ImageFont.truetype(Config.FONT_BOLD, title_font.size - 5)
            
        headline_pos = (center_x, sign_y + 80) 
        
        # --- BODY PREP ---
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
            canvas.paste(title_shadow, (8, 8), title_shadow) 

        # Body Shadow (Light, Minimal offset)
        body_shadow = make_shadow(body_layer, blur_radius=2)
        if body_shadow:
            canvas.paste(body_shadow, (2, 2), body_shadow) 

        # Paste Main Layers
        canvas.paste(title_layer, (0, 0), title_layer)
        canvas.paste(body_layer, (0, 0), body_layer)
        
        overlay_path = os.path.join(Config.TEMP_DIR, "overlay.png")
        canvas.save(overlay_path)
        return overlay_path

    def _gaussian_blur(self, image):
        """Applies strong Gaussian Blur to a frame using PIL"""
        return np.array(Image.fromarray(image).filter(ImageFilter.GaussianBlur(radius=15)))

    def render_video(self, input_path: str, headline: str, body: str, layout_mode: str = 'lower', progress_callback=None) -> str:
        """
        Renders the final video.
        layout_mode: 'lower' (crop top, center low) or 'standard' (no crop, center mid).
        """
        print(f"🎨 Rendering video ({layout_mode})...")
        
        def make_even(n):
            n = int(n)
            return n if n % 2 == 0 else n + 1

        try:
            overlay_path = self._create_overlay(headline, body)
            
            # Video Processing
            with VideoFileClip(input_path) as clip:
                # Target dimensions (ensure even)
                target_w = make_even(Config.VIDEO_SIZE[0])
                target_h = make_even(Config.VIDEO_SIZE[1])
                
                # Background (Solid Black)
                bg_clip = ColorClip(size=(target_w, target_h), color=(0, 0, 0)).set_duration(clip.duration)
                
                # Main Content
                # Resize to fit width
                main_clip = clip.resize(width=target_w)
                # Force even height after aspect-ratio resize
                main_clip = main_clip.resize(height=make_even(main_clip.h))
                
                # LAYOUT LOGIC
                if layout_mode == 'lower':
                    # Crop top (TikTok captions area)
                    crop_y = 180
                    if main_clip.h > crop_y + 100: # Ensure we don't crop a tiny video to death
                        main_clip = main_clip.crop(y1=crop_y)
                        main_clip = main_clip.resize(height=make_even(main_clip.h))
                    
                    # Position LOW
                    target_center_y = 1250
                    
                    # Background source (also crop top to hide junk in blur)
                    bg_source_clip = clip.crop(y1=min(crop_y, clip.h - 10))
                else:
                    target_center_y = target_h // 2
                    bg_source_clip = clip
                
                # Calculate position
                top_pos = int(target_center_y - (main_clip.h / 2))
                
                # --- PREVENT BANNER OVERLAP ---
                # Banner ends around y=600. If video starts higher, crop it.
                banner_safe_y = 620
                if top_pos < banner_safe_y:
                    overlap = banner_safe_y - top_pos
                    if main_clip.h > overlap + 50:
                        main_clip = main_clip.crop(y1=int(overlap))
                        main_clip = main_clip.resize(height=make_even(main_clip.h))
                        top_pos = banner_safe_y

                main_clip = main_clip.set_position(("center", int(top_pos)))

                # Blurred Background (Fills screen)
                # Resize to fill screen height then crop width
                bg_video_clip = bg_source_clip.resize(height=target_h)
                if bg_video_clip.w < target_w:
                    bg_video_clip = bg_video_clip.resize(width=target_w)
                
                # Ensure even width before crop
                bg_video_clip = bg_video_clip.resize(width=make_even(bg_video_clip.w))
                    
                bg_video_clip = bg_video_clip.crop(x_center=int(bg_video_clip.w/2), y_center=int(bg_video_clip.h/2), 
                                                   width=target_w, height=target_h)
                
                # Apply Blur
                bg_video_clip = bg_video_clip.fl_image(self._gaussian_blur)
                bg_video_clip = bg_video_clip.set_opacity(0.4).set_position("center")
                
                # Overlay (Banner + Text)
                overlay_clip = ImageClip(overlay_path).set_duration(clip.duration).set_position("center")
                
                # Composite
                final = CompositeVideoClip([bg_clip, bg_video_clip, main_clip, overlay_clip], size=(target_w, target_h))
                final = final.set_duration(clip.duration) 
                
                output_path = os.path.join(Config.OUTPUT_DIR, f"final_{os.path.basename(input_path)}")
                
                # Write file
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