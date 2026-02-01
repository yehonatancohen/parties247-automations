"""
Instagram Authentication Service using Instagrapi

Uses the instagrapi library for direct Instagram API access:
- Username/password login
- 2FA code verification  
- Session storage and reuse
- Direct video download capability
"""

import os
import json
from typing import Optional, Callable, Awaitable
from config import Config

# Will be imported on first use to avoid import errors if not installed
_Client = None

def _get_client_class():
    """Lazy import of instagrapi Client."""
    global _Client
    if _Client is None:
        from instagrapi import Client
        _Client = Client
    return _Client


class InstagramAuth:
    """Instagram authentication manager using instagrapi."""
    
    _instance = None
    _client = None
    _is_logged_in = False
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self._is_logged_in = False
        self._client = None
    
    def _get_client(self):
        """Get or create the Instagram client."""
        if self._client is None:
            Client = _get_client_class()
            self._client = Client()
            # Set some default settings for reliability
            self._client.delay_range = [1, 3]
        return self._client
    
    def _get_session_file(self) -> str:
        """Get the session file path."""
        return os.path.join(Config.INSTAGRAM_SESSION_DIR, "session.json")
    
    @staticmethod
    def has_saved_session() -> bool:
        """Check if we have a saved session."""
        session_file = os.path.join(Config.INSTAGRAM_SESSION_DIR, "session.json")
        return os.path.exists(session_file)
    
    def clear_session(self):
        """Clear saved session (logout)."""
        session_file = self._get_session_file()
        if os.path.exists(session_file):
            os.remove(session_file)
        
        # Also clear cookies file if exists
        if os.path.exists(Config.INSTAGRAM_COOKIES_FILE):
            os.remove(Config.INSTAGRAM_COOKIES_FILE)
        
        self._client = None
        self._is_logged_in = False
        print("[INFO] Instagram session cleared")
    
    def _save_session(self):
        """Save session to file."""
        if self._client:
            os.makedirs(Config.INSTAGRAM_SESSION_DIR, exist_ok=True)
            session_file = self._get_session_file()
            self._client.dump_settings(session_file)
            print("[INFO] Instagram session saved")
    
    def _load_session(self) -> bool:
        """Load session from file. Returns True if successful."""
        session_file = self._get_session_file()
        if not os.path.exists(session_file):
            return False
        
        try:
            client = self._get_client()
            client.load_settings(session_file)
            
            # Verify the session is still valid
            client.get_timeline_feed()
            self._is_logged_in = True
            print("[INFO] Loaded existing Instagram session")
            return True
        except Exception as e:
            print(f"[WARN] Failed to load session: {e}")
            self._client = None
            return False
    
    async def login(
        self, 
        username: str, 
        password: str, 
        on_2fa_required: Optional[Callable[[], Awaitable[str]]] = None
    ) -> dict:
        """
        Login to Instagram with username and password.
        
        Args:
            username: Instagram username
            password: Instagram password
            on_2fa_required: Async callback that returns the 2FA/verification code
        
        Returns:
            dict with 'success' (bool), 'message' (str), and optionally 'needs_2fa' (bool)
        """
        import asyncio
        
        try:
            client = self._get_client()
            
            # Try to login
            print(f"[INFO] Attempting Instagram login for {username}...")
            
            # instagrapi handles 2FA through a callback
            verification_code = None
            
            def handle_2fa_challenge(username, choice):
                """Called when 2FA is required."""
                # choice is typically the verification method (e.g., 'sms', 'email')
                print(f"[INFO] 2FA required for {username}, method: {choice}")
                return verification_code
            
            # If 2FA callback is provided, we need to handle it specially
            if on_2fa_required:
                # First attempt without 2FA
                try:
                    client.login(username, password)
                    self._is_logged_in = True
                    self._save_session()
                    return {'success': True, 'message': 'Login successful!'}
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    # Check if it's a 2FA challenge
                    if 'challenge' in error_msg or 'two-factor' in error_msg or 'verification' in error_msg or 'code' in error_msg:
                        print("[INFO] 2FA verification required...")
                        
                        # Get the code from user via callback
                        code = await on_2fa_required()
                        
                        if not code:
                            return {'success': False, 'message': '2FA code not provided'}
                        
                        # Try login with verification code
                        try:
                            client.login(username, password, verification_code=code)
                            self._is_logged_in = True
                            self._save_session()
                            return {'success': True, 'message': 'Login successful with 2FA!'}
                        except Exception as e2:
                            return {'success': False, 'message': f'2FA verification failed: {str(e2)}'}
                    else:
                        return {'success': False, 'message': f'Login failed: {str(e)}'}
            else:
                # Simple login without 2FA handling
                client.login(username, password)
                self._is_logged_in = True
                self._save_session()
                return {'success': True, 'message': 'Login successful!'}
                
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] Instagram login failed: {error_msg}")
            
            # Check for specific error types
            if 'challenge' in error_msg.lower():
                return {
                    'success': False, 
                    'message': 'Instagram requires verification. Please try again.',
                    'needs_2fa': True
                }
            elif 'password' in error_msg.lower():
                return {'success': False, 'message': 'Invalid password'}
            elif 'user' in error_msg.lower():
                return {'success': False, 'message': 'User not found'}
            else:
                return {'success': False, 'message': f'Login error: {error_msg}'}
    
    def login_with_session(self) -> bool:
        """
        Try to login using saved session.
        Returns True if successful, False otherwise.
        """
        return self._load_session()
    
    def get_logged_in_client(self):
        """
        Get the logged-in client instance.
        Returns None if not logged in.
        """
        if not self._is_logged_in:
            if not self._load_session():
                return None
        return self._client
    
    def download_video(self, url: str, output_path: str) -> Optional[str]:
        """
        Download a video using the authenticated client.
        
        Args:
            url: Instagram URL (reel, post, etc.)
            output_path: Where to save the video
            
        Returns:
            Path to downloaded file, or None if failed
        """
        import re
        
        client = self.get_logged_in_client()
        if not client:
            return None
        
        try:
            # Extract media ID or shortcode from URL
            # Patterns: /reel/ABC123/, /p/ABC123/, /reels/ABC123/
            shortcode_match = re.search(r'/(?:p|reel|reels)/([A-Za-z0-9_-]+)', url)
            if not shortcode_match:
                print("[WARN] Could not extract shortcode from URL")
                return None
            
            shortcode = shortcode_match.group(1)
            
            # Get media PK from shortcode
            media_pk = client.media_pk_from_code(shortcode)
            
            # Get media info
            media_info = client.media_info(media_pk)
            
            # Download based on media type
            if media_info.media_type == 2:  # Video
                path = client.video_download(media_pk, folder=os.path.dirname(output_path))
                # Rename to our desired output path
                if path and os.path.exists(str(path)):
                    import shutil
                    shutil.move(str(path), output_path)
                    return output_path
            elif media_info.media_type == 1:  # Photo
                print("[INFO] Media is a photo, not a video")
                return None
            elif media_info.media_type == 8:  # Album/Carousel
                # Try to find video in carousel
                for resource in media_info.resources:
                    if resource.video_url:
                        path = client.video_download_by_url(str(resource.video_url), folder=os.path.dirname(output_path))
                        if path and os.path.exists(str(path)):
                            import shutil
                            shutil.move(str(path), output_path)
                            return output_path
                print("[INFO] No video found in carousel")
                return None
                
        except Exception as e:
            print(f"[ERROR] Failed to download via instagrapi: {e}")
            return None
        
        return None
    
    def get_cookies_for_ytdlp(self) -> Optional[str]:
        """
        Get cookies in Netscape format for yt-dlp.
        Returns path to temp cookies file, or None if not logged in.
        """
        client = self.get_logged_in_client()
        if not client:
            return None
        
        try:
            # Get session cookies from instagrapi
            settings = client.get_settings()
            cookies = settings.get('cookies', {})
            
            if not cookies:
                return None
            
            # Convert to Netscape format
            netscape_file = os.path.join(Config.TEMP_DIR, "instagram_cookies_netscape.txt")
            
            with open(netscape_file, 'w') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Generated by instagrapi session\n\n")
                
                for name, value in cookies.items():
                    # Format: domain, flag, path, secure, expiration, name, value
                    domain = ".instagram.com"
                    f.write(f"{domain}\tTRUE\t/\tTRUE\t0\t{name}\t{value}\n")
            
            return netscape_file
            
        except Exception as e:
            print(f"[WARN] Could not export cookies for yt-dlp: {e}")
            return None


# Singleton accessor
def get_instagram_auth() -> InstagramAuth:
    return InstagramAuth.get_instance()
