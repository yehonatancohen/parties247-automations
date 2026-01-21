import os
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, features
import numpy as np

# --- MONKEY PATCHES ---
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# Check for Raqm support
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

# --- PILMOJI IMPORTS (Smart Fallback Logic) ---
try:
    from pilmoji import Pilmoji
    from pilmoji.source import AppleEmojiSource, TwitterEmojiSource
    PILMOJI_AVAILABLE = True
except ImportError:
    PILMOJI_AVAILABLE = False
    print("Warning: pilmoji not installed. Emojis may not render correctly.")

class GraphicsEngine:
    def __init__(self):
        try:
            print(f"[INFO] PIL Raqm support: {RAQM_SUPPORT}")
        except Exception as e:
            print(f"[WARN] Could not check PIL features: {e}")

        # --- TEXT POSITIONING ---
        self.text_start_y = 350   
        self.sign_height = 400    
        
        self._load_assets()

    def _load_assets(self):
        overlay_path = getattr(Config, "READY_OVERLAY_PATH", os.path.join(Config.ASSETS_DIR, "overlay_template.png"))
        
        print(f"[INFO] Loading ready overlay from: {overlay_path}")
        if not os.path.exists(overlay_path):
             print(f"[WARN] Overlay template not found. Using fallback.")
             overlay_path = Config.WOOD_IMAGE_PATH
        
        self.overlay_base = Image.open(overlay_path).convert("RGBA")
        
        target_width = Config.VIDEO_SIZE[0]
        if self.overlay_base.width != target_width:
            aspect_ratio = self.overlay_base.height / self.overlay_base.width
            new_height = int(target_width * aspect_ratio)
            self.overlay_base = self.overlay_base.resize((target_width, new_height), Image.Resampling.LANCZOS)
            
        self.overlay_height = self.overlay_base.height

        try:
            self.title_font = ImageFont.truetype(Config.FONT_BOLD, 105) 
            self.body_font = ImageFont.truetype(Config.FONT_REGULAR, 60)
        except OSError as e:
            raise FileNotFoundError(f"Fonts not found: {e}")

    def _create_overlay(self, headline: str, body: str) -> str:
        canvas = self.overlay_base.copy()
        text_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        
        # Initialize Pilmoji with APPLE source
        if PILMOJI_AVAILABLE:
            text_pilmoji = Pilmoji(text_layer, source=AppleEmojiSource)
        else:
            text_pilmoji = None
            
        center_x = canvas.width // 2
        safe_width = int(canvas.width * 0.8)
        sign_y = self.text_start_y
        
        # --- HEADLINE PREP ---
        title_font = self.title_font
        
        if RAQM_SUPPORT:
            headline_processed = headline
        else:
            headline_processed = TextUtils.process_hebrew(headline)
        
        while title_font.getlength(headline_processed) > safe_width and title_font.size > 40:
            title_font = ImageFont.truetype(Config.FONT_BOLD, title_font.size - 5)
            
        headline_pos = (center_x, sign_y + 80) 
        
        # --- BODY PREP ---
        def wrap_paragraph(text, font, max_width):
            lines = []
            words = text.split()
            current_line = []
            for word in words:
                test_line_words = current_line + [word]
                raw_test_line = ' '.join(test_line_words)
                
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

        body_start_y = sign_y + 150
        max_body_y = sign_y + self.sign_height - 45 
        max_available_height = max_body_y - body_start_y
        
        current_body_size = 60
        min_body_size = 25
        final_body_font = None
        final_body_lines = []
        
        while current_body_size >= min_body_size:
            temp_font = ImageFont.truetype(Config.FONT_REGULAR, current_body_size)
            lines = process_body_text(body, temp_font, safe_width)
            
            ascent, descent = temp_font.getmetrics()
            line_height = ascent + descent + 4 
            total_height = len(lines) * line_height
            
            if total_height <= max_available_height or current_body_size == min_body_size:
                final_body_font = temp_font
                final_body_lines = lines
                break
            current_body_size -= 2
            
        if final_body_font is None:
            final_body_font = ImageFont.truetype(Config.FONT_REGULAR, min_body_size)
            final_body_lines = process_body_text(body, final_body_font, safe_width)

        # --- DRAWING (Apple -> Twitter Fallback) ---
        def draw_centered(manager, layer, position, text, font, fill, stroke_width, stroke_fill):
            if PILMOJI_AVAILABLE and manager:
                try:
                    w, h = manager.getsize(text, font=font)
                    start_x = position[0] - (w // 2)
                    start_y = position[1] - (h // 2) + 5 
                    manager.text((start_x, start_y), text, font=font, fill=fill, 
                                 stroke_width=stroke_width, stroke_fill=stroke_fill)
                except Exception as e:
                    print(f"🍎 Apple Emoji failed for '{text}'. Switching to Twitter.")
                    try:
                        with Pilmoji(layer, source=TwitterEmojiSource) as fallback_manager:
                            w, h = fallback_manager.getsize(text, font=font)
                            start_x = position[0] - (w // 2)
                            start_y = position[1] - (h // 2) + 5
                            fallback_manager.text((start_x, start_y), text, font=font, fill=fill, 
                                                  stroke_width=stroke_width, stroke_fill=stroke_fill)
                    except Exception as e2:
                        d = ImageDraw.Draw(layer)
                        d.text(position, text, font=font, fill=fill, anchor="mm", 
                               stroke_width=stroke_width, stroke_fill=stroke_fill)
            else:
                d = ImageDraw.Draw(layer)
                d.text(position, text, font=font, fill=fill, anchor="mm", 
                       stroke_width=stroke_width, stroke_fill=stroke_fill)

        draw_centered(text_pilmoji, text_layer, headline_pos, headline_processed, title_font, "white", 3, "black")
        
        current_y = body_start_y
        ascent, descent = final_body_font.getmetrics()
        line_height = ascent + descent + 4
        
        for line in final_body_lines:
             if RAQM_SUPPORT:
                 processed_line = line
             else:
                 processed_line = TextUtils.process_hebrew(line)
             
             line_center_y = int(current_y + line_height/2)
             pos = (center_x, line_center_y)
             draw_centered(text_pilmoji, text_layer, pos, processed_line, final_body_font, "#f0f0f0", 3, "black")
             current_y += line_height

        def make_shadow(layer, blur_radius):
            if layer.getbbox():
                alpha = layer.split()[3]
                shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                shadow.paste((0, 0, 0, 255), (0, 0), mask=alpha)
                return shadow.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            return None

        text_shadow = make_shadow(text_layer, blur_radius=3)
        if text_shadow:
            canvas.paste(text_shadow, (3, 3), text_shadow)
        canvas.paste(text_layer, (0, 0), text_layer)
        
        overlay_path = os.path.join(Config.TEMP_DIR, "overlay.png")
        canvas.save(overlay_path)
        return overlay_path

    def render_video(self, input_path: str, headline: str, body: str, layout_mode: str = 'lower', progress_callback=None) -> str:
        """
        Renders the final video using FFmpeg with advanced Anti-Detection filters.
        """
        import subprocess
        import json
        import imageio_ffmpeg
        
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        print(f"[INFO] Rendering video ({layout_mode})...")
        
        overlay_path = self._create_overlay(headline, body)
        
        base_name = os.path.basename(input_path)
        output_filename = f"final_{base_name}"
        output_path = os.path.join(Config.OUTPUT_DIR, output_filename)

        if layout_mode == 'lower':
            try:
                # Get video duration
                cmd = [
                    'ffprobe',
                    '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    input_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                duration = float(result.stdout)
                
                # Calculate the middle of the video
                clip_duration = 5 # seconds
                start_time = max(0, (duration / 2) - (clip_duration / 2))

                # Calculate shift: Middle of (Screen Bottom + Banner Bottom) - Middle of Screen
                shift_y = int((self.text_start_y + self.sign_height) / 2)
                
                video_filters = (
                    f"trim=start={start_time}:duration={clip_duration},setpts=PTS-STARTPTS,"
                    "crop=in_w:1920:0:(in_h-1920)/2,"
                    "scale=1080:1920,"
                    "eq=gamma=1.03:saturation=1.05:contrast=1.02,"
                    "noise=alls=1.5:allf=t,"
                    "vignette=PI/20,"
                    "unsharp=3:3:0.5"
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                 video_filters = (
                    "setpts=PTS/1.05,"
                    "crop=in_w*0.96:in_h*0.96,"
                    "scale=1080:1920,"
                    "eq=gamma=1.03:saturation=1.05:contrast=1.02,"
                    "noise=alls=1.5:allf=t,"
                    "vignette=PI/20,"
                    "unsharp=3:3:0.5"
                )
        else:
            shift_y = 0
            video_filters = (
                "setpts=PTS/1.05,"
                "crop=in_w*0.96:in_h*0.96,"
                "scale=1080:1920,"
                "eq=gamma=1.03:saturation=1.05:contrast=1.02,"
                "noise=alls=1.5:allf=t,"
                "vignette=PI/20,"
                "unsharp=3:3:0.5"
            )
        
        audio_filters = (
            "atempo=1.05,"
            "volume=0.98,"
            "highpass=f=15,"
            "lowpass=f=19000"
        )
        
        # Apply shift only for 'lower' mode logic (which is captured by shift_y > 0 if derived from layout)
        # However, layout_mode determines shift. 
        # Re-evaluating shift based on mode for clarity in main_transform construction
        if layout_mode == 'lower':
             shift_val = int((self.text_start_y + self.sign_height) / 2)
             main_transform = f"pad=1080:{1920+shift_val}:0:{shift_val}:black,crop=1080:1920:0:0,"
        else:
             main_transform = ""

        ffmpeg_cmd = [
            ffmpeg_exe,
            '-i', input_path,
            '-i', overlay_path,
            '-filter_complex',
            f"[0:v]{video_filters}[v_proc];" +
            f"[0:a]{audio_filters}[a_proc];" +
            f"[v_proc]split[v_to_main][v_copy];" +
            f"[v_to_main]{main_transform}drawbox=0:0:1080:{self.text_start_y + 70}:color=black:t=fill[v_masked];" +
            f"[v_copy]crop=1080:{self.text_start_y + 70}:0:(in_h-{self.text_start_y + 70})/2+300,format=rgba,colorchannelmixer=aa=0.25[v_filler];" +
            f"[v_masked][v_filler]overlay=0:0[v_staged];" +
            f"[v_staged][1:v]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[out]",
            '-map', '[out]',
            '-map', '[a_proc]',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'medium',
            '-b:v', '2500k',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-map_metadata', '-1',
            '-y', 
            output_path
        ]

        try:
            print(f"[INFO] Saving video to: {output_path}")
            subprocess.run(ffmpeg_cmd, check=True)
            return output_path
        except FileNotFoundError:
            print("[WARN] ffmpeg not found. Video not rendered.")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"Error in render_video: {e}")
            raise e