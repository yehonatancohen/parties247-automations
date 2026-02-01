"""
Instagram client wrapper using instagrapi.
Handles authentication, session persistence, and story uploads with link stickers.
"""

import os
import base64
import json
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from instagrapi import Client
from instagrapi.types import StoryLink

from config import Config


class InstagramClient:
    """Instagram API client wrapper with session persistence."""
    
    def __init__(self):
        self.client = Client()
        self.logged_in = False
        self._setup_client()
    
    def _setup_client(self):
        """Configure client settings."""
        # Set device settings for more realistic requests
        self.client.set_locale("he_IL")
        self.client.set_timezone_offset(2 * 3600)  # Israel timezone (UTC+2)
    
    def _parse_netscape_cookies(self, cookie_content: str) -> dict:
        """Parse Netscape format cookies into a dict for instagrapi."""
        cookies = {}
        for line in cookie_content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) >= 7:
                name = parts[5]
                value = parts[6]
                cookies[name] = value
        return cookies
    
    def _login_with_cookies(self) -> bool:
        """
        Try to login using INSTAGRAM_COOKIES env var.
        Returns True if successful, False otherwise.
        """
        cookies_content = os.environ.get('INSTAGRAM_COOKIES')
        if not cookies_content:
            return False
        
        try:
            # Decode base64 if needed
            try:
                decoded = base64.b64decode(cookies_content).decode('utf-8')
                cookies_content = decoded
            except:
                pass  # Not base64, use as-is
            
            # Parse Netscape cookies format
            cookies = self._parse_netscape_cookies(cookies_content)
            
            if not cookies.get('sessionid') or not cookies.get('ds_user_id'):
                print("⚠️ INSTAGRAM_COOKIES missing required cookies (sessionid, ds_user_id)")
                return False
            
            print("🔐 Logging in with INSTAGRAM_COOKIES env var...")
            
            # Set cookies directly on the client
            self.client.set_settings({
                "cookies": cookies,
                "authorization_data": {
                    "ds_user_id": cookies.get('ds_user_id', ''),
                    "sessionid": cookies.get('sessionid', '')
                }
            })
            
            # Verify the session works
            user_id = cookies.get('ds_user_id')
            self.client.user_info(int(user_id))
            
            self.logged_in = True
            print("✅ Instagram login successful (via cookies)")
            
            # Save session for future use
            session_file = Path(Config.DATA_DIR) / Config.INSTAGRAM_SESSION_FILE
            Config.ensure_dirs()
            self.client.dump_settings(str(session_file))
            
            return True
            
        except Exception as e:
            print(f"⚠️ Cookie-based login failed: {e}")
            return False
    
    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Login to Instagram with session persistence.
        Priority: 1. INSTAGRAM_COOKIES env var, 2. Existing session, 3. Username/password
        Returns True if login successful.
        """
        # First try cookies from env var
        if self._login_with_cookies():
            return True
        
        # Then try existing session or username/password
        username = username or Config.INSTAGRAM_USERNAME
        password = password or Config.INSTAGRAM_PASSWORD
        
        if not username or not password:
            raise ValueError("Instagram credentials not configured and INSTAGRAM_COOKIES not set")
        
        session_file = Path(Config.DATA_DIR) / Config.INSTAGRAM_SESSION_FILE
        
        # Try to load existing session
        if session_file.exists():
            try:
                print("📱 Loading existing Instagram session...")
                self.client.load_settings(str(session_file))
                self.client.login(username, password)
                
                # Verify session is valid by making a simple request
                self.client.user_id_from_username(username)
                self.logged_in = True
                print("✅ Instagram session restored successfully")
                return True
            except Exception as e:
                print(f"⚠️ Session restore failed: {e}")
                # Session invalid, will do fresh login
        
        # Fresh login
        try:
            print("🔐 Logging into Instagram...")
            self.client.login(username, password)
            
            # Save session for future use
            Config.ensure_dirs()
            self.client.dump_settings(str(session_file))
            
            self.logged_in = True
            print("✅ Instagram login successful")
            return True
            
        except Exception as e:
            print(f"❌ Instagram login failed: {e}")
            raise
    
    def create_story_image(
        self, 
        image_path: str, 
        link_text: str = "קנה כאן 🛒",
        output_path: Optional[str] = None
    ) -> str:
        """
        Create a story-ready image with Hebrew text overlay.
        
        Args:
            image_path: Path to the source image
            link_text: Hebrew text to overlay (with emoji)
            output_path: Where to save the result (default: temp dir)
        
        Returns:
            Path to the processed image
        """
        # Load and resize image to story dimensions
        img = Image.open(image_path).convert("RGBA")
        
        # Resize to fit story dimensions while maintaining aspect ratio
        target_size = Config.STORY_SIZE
        img_ratio = img.width / img.height
        target_ratio = target_size[0] / target_size[1]
        
        if img_ratio > target_ratio:
            # Image is wider - fit to width
            new_width = target_size[0]
            new_height = int(new_width / img_ratio)
        else:
            # Image is taller - fit to height
            new_height = target_size[1]
            new_width = int(new_height * img_ratio)
        
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create background and paste image centered
        background = Image.new("RGBA", target_size, (0, 0, 0, 255))
        paste_x = (target_size[0] - new_width) // 2
        paste_y = (target_size[1] - new_height) // 2
        background.paste(img, (paste_x, paste_y))
        
        # Add text overlay at the bottom
        draw = ImageDraw.Draw(background)
        
        # Load font
        try:
            font = ImageFont.truetype(Config.FONT_BOLD, 48)
        except:
            # Fallback to default font
            font = ImageFont.load_default()
        
        # Calculate text position (bottom center)
        text_bbox = draw.textbbox((0, 0), link_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        text_x = (target_size[0] - text_width) // 2
        text_y = int(target_size[1] * 0.88) - text_height // 2
        
        # Draw text background (semi-transparent)
        padding = 20
        bg_rect = [
            text_x - padding,
            text_y - padding,
            text_x + text_width + padding,
            text_y + text_height + padding
        ]
        draw.rectangle(bg_rect, fill=(0, 0, 0, 180))
        
        # Draw text
        draw.text((text_x, text_y), link_text, font=font, fill=(255, 255, 255, 255))
        
        # Save result
        if output_path is None:
            output_path = os.path.join(Config.TEMP_DIR, "story_prepared.png")
        
        Config.ensure_dirs()
        background.convert("RGB").save(output_path, "PNG")
        
        return output_path
    
    def upload_story(
        self,
        image_path: str,
        link_url: str,
        link_text: str = "קנה כאן 🛒",
        add_text_overlay: bool = True
    ) -> bool:
        """
        Upload an image as an Instagram story with a link sticker.
        
        Args:
            image_path: Path to the image file
            link_url: URL for the link sticker
            link_text: Text to show on the story (Hebrew)
            add_text_overlay: Whether to add text overlay to the image
        
        Returns:
            True if upload successful
        """
        if not self.logged_in:
            raise RuntimeError("Not logged in to Instagram")
        
        # Prepare image if needed
        if add_text_overlay:
            prepared_image = self.create_story_image(image_path, link_text)
        else:
            prepared_image = image_path
        
        try:
            print(f"📤 Uploading story with link: {link_url}")
            
            # Create link sticker
            links = [
                StoryLink(
                    webUri=link_url,
                    x=Config.LINK_STICKER_X,
                    y=Config.LINK_STICKER_Y,
                    width=Config.LINK_STICKER_WIDTH,
                    height=Config.LINK_STICKER_HEIGHT,
                )
            ]
            
            # Upload story
            self.client.photo_upload_to_story(
                prepared_image,
                links=links
            )
            
            print("✅ Story uploaded successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Story upload failed: {e}")
            raise
        
        finally:
            # Cleanup temp file
            if add_text_overlay and os.path.exists(prepared_image):
                try:
                    os.remove(prepared_image)
                except:
                    pass
    
    def logout(self):
        """Logout and clear session."""
        try:
            self.client.logout()
        except:
            pass
        self.logged_in = False
