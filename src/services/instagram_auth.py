"""
Instagram Authentication Service

Handles Instagram login via Playwright with support for:
- Username/password login
- 2FA code verification
- Session cookie storage and reuse
"""

import os
import json
import asyncio
from playwright.async_api import async_playwright
from config import Config


class InstagramAuth:
    """Instagram authentication manager using Playwright."""
    
    _instance = None
    _browser = None
    _context = None
    _page = None
    _is_logged_in = False
    _pending_2fa_callback = None
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self._is_logged_in = False
        self._pending_2fa_callback = None
    
    @staticmethod
    def has_saved_session() -> bool:
        """Check if we have a saved session (cookies)."""
        return os.path.exists(Config.INSTAGRAM_COOKIES_FILE)
    
    @staticmethod
    def clear_session():
        """Clear saved session (logout)."""
        if os.path.exists(Config.INSTAGRAM_COOKIES_FILE):
            os.remove(Config.INSTAGRAM_COOKIES_FILE)
            print("[INFO] Instagram session cleared")
    
    @staticmethod
    def save_cookies(cookies: list):
        """Save cookies to file."""
        os.makedirs(Config.INSTAGRAM_SESSION_DIR, exist_ok=True)
        with open(Config.INSTAGRAM_COOKIES_FILE, 'w') as f:
            json.dump(cookies, f)
        print("[INFO] Instagram cookies saved")
    
    @staticmethod
    def load_cookies() -> list:
        """Load cookies from file."""
        if os.path.exists(Config.INSTAGRAM_COOKIES_FILE):
            with open(Config.INSTAGRAM_COOKIES_FILE, 'r') as f:
                return json.load(f)
        return []
    
    async def login(self, username: str, password: str, on_2fa_required=None) -> dict:
        """
        Login to Instagram with username and password.
        
        Args:
            username: Instagram username
            password: Instagram password
            on_2fa_required: Async callback function that will be called if 2FA is needed.
                            Should return the 2FA code as a string.
        
        Returns:
            dict with 'success' (bool) and 'message' (str)
        """
        playwright = None
        browser = None
        
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 720}
            )
            page = await context.new_page()
            
            print("[INFO] Navigating to Instagram login page...")
            await page.goto('https://www.instagram.com/accounts/login/', wait_until='networkidle', timeout=60000)
            
            # Wait for login form
            await page.wait_for_selector('input[name="username"]', timeout=30000)
            
            # Accept cookies if dialog appears
            try:
                accept_btn = page.locator('button:has-text("Allow all cookies"), button:has-text("Accept")')
                if await accept_btn.count() > 0:
                    await accept_btn.first.click()
                    await asyncio.sleep(1)
            except:
                pass
            
            print("[INFO] Entering credentials...")
            await page.fill('input[name="username"]', username)
            await page.fill('input[name="password"]', password)
            
            # Click login button
            await page.click('button[type="submit"]')
            
            # Wait for response - could be success, 2FA, or error
            await asyncio.sleep(3)
            
            # Check for various outcomes
            # 1. Check for error message
            error_msgs = page.locator('#slfErrorAlert, [role="alert"], p[data-testid="login-error-message"]')
            if await error_msgs.count() > 0:
                error_text = await error_msgs.first.inner_text()
                return {'success': False, 'message': f'Login failed: {error_text}'}
            
            # 2. Check for 2FA verification
            try:
                # Check multiple possible 2FA indicators
                twofa_indicators = [
                    'input[name="verificationCode"]',
                    'input[name="approvals_code"]',
                    'input[aria-label*="security code"]',
                    'input[placeholder*="Code"]',
                ]
                
                is_2fa = False
                for selector in twofa_indicators:
                    if await page.locator(selector).count() > 0:
                        is_2fa = True
                        break
                
                # Also check for 2FA text
                page_text = await page.content()
                if 'security code' in page_text.lower() or 'verification code' in page_text.lower():
                    is_2fa = True
                
                if is_2fa:
                    print("[INFO] 2FA verification required")
                    
                    if on_2fa_required is None:
                        return {
                            'success': False, 
                            'message': '2FA required but no callback provided',
                            'needs_2fa': True
                        }
                    
                    # Request 2FA code from user
                    code = await on_2fa_required()
                    
                    if not code:
                        return {'success': False, 'message': '2FA code not provided'}
                    
                    # Find and fill the 2FA input
                    for selector in twofa_indicators:
                        input_field = page.locator(selector)
                        if await input_field.count() > 0:
                            await input_field.fill(code)
                            break
                    
                    # Click verify/confirm button
                    confirm_btns = ['button:has-text("Confirm")', 'button:has-text("Verify")', 'button[type="submit"]']
                    for btn_selector in confirm_btns:
                        btn = page.locator(btn_selector)
                        if await btn.count() > 0:
                            await btn.first.click()
                            break
                    
                    await asyncio.sleep(3)
            except Exception as e:
                print(f"[WARN] 2FA check error: {e}")
            
            # 3. Check if we're now logged in (look for home page elements)
            await asyncio.sleep(2)
            current_url = page.url
            
            # Success indicators
            if 'challenge' not in current_url and '/accounts/login' not in current_url:
                # Try to verify by checking for home page elements
                try:
                    # Wait for some indicator that we're logged in
                    await page.wait_for_selector('svg[aria-label="Home"], a[href="/"], nav', timeout=10000)
                    
                    # Save cookies
                    cookies = await context.cookies()
                    self.save_cookies(cookies)
                    self._is_logged_in = True
                    
                    print("[INFO] Instagram login successful!")
                    return {'success': True, 'message': 'Login successful!'}
                except:
                    pass
            
            # Check for "Save login info" prompt - this means login succeeded
            if 'Save Your Login Info' in await page.content() or 'save-device' in current_url:
                cookies = await context.cookies()
                self.save_cookies(cookies)
                self._is_logged_in = True
                return {'success': True, 'message': 'Login successful!'}
            
            # If we get here, something went wrong
            return {'success': False, 'message': 'Login failed - unknown state. Check if credentials are correct.'}
            
        except Exception as e:
            print(f"[ERROR] Instagram login failed: {e}")
            return {'success': False, 'message': f'Login error: {str(e)}'}
        
        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
    
    async def verify_session(self) -> bool:
        """
        Verify if the saved session is still valid.
        Returns True if logged in, False otherwise.
        """
        if not self.has_saved_session():
            return False
        
        playwright = None
        browser = None
        
        try:
            playlist = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            # Load saved cookies
            cookies = self.load_cookies()
            await context.add_cookies(cookies)
            
            page = await context.new_page()
            await page.goto('https://www.instagram.com/', wait_until='networkidle', timeout=30000)
            
            # Check if we're logged in
            current_url = page.url
            if '/accounts/login' in current_url:
                self._is_logged_in = False
                return False
            
            # Try to find logged-in indicators
            try:
                await page.wait_for_selector('svg[aria-label="Home"], a[href="/explore/"]', timeout=5000)
                self._is_logged_in = True
                return True
            except:
                self._is_logged_in = False
                return False
                
        except Exception as e:
            print(f"[WARN] Session verification failed: {e}")
            return False
        
        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
    
    def get_cookies_for_ytdlp(self) -> str:
        """
        Get cookies in Netscape format for yt-dlp.
        Returns path to temp cookies file.
        """
        if not self.has_saved_session():
            return None
        
        cookies = self.load_cookies()
        if not cookies:
            return None
        
        # Convert to Netscape format
        netscape_file = os.path.join(Config.TEMP_DIR, "instagram_cookies_netscape.txt")
        
        with open(netscape_file, 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This file was generated automatically\n\n")
            
            for cookie in cookies:
                # Netscape format: domain, flag, path, secure, expiration, name, value
                domain = cookie.get('domain', '.instagram.com')
                flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                path = cookie.get('path', '/')
                secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                expiry = int(cookie.get('expires', 0))
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                
                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
        
        return netscape_file


# Singleton accessor
def get_instagram_auth() -> InstagramAuth:
    return InstagramAuth.get_instance()
