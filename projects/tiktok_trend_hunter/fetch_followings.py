"""
Fetch the following list of a TikTok user via UI Automation.

Usage:
    python fetch_followings.py <username> [limit]

Example:
    python fetch_followings.py yehonatancohen976 200

IMPORTANT:
    This script automates the browser UI to click 'Following' and scroll.
    It requires TIKTOK_SESSION_ID in .env.test to be valid.
"""

import asyncio
import os
import sys
import random

from dotenv import load_dotenv
from playwright.async_api import async_playwright

# ── Paths & env ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
USERS_FILE = os.path.join(SCRIPT_DIR, "users.txt")

for env_name in (".env.test", ".env"):
    p = os.path.join(PROJECT_ROOT, env_name)
    if os.path.exists(p):
        load_dotenv(p)
        break

TIKTOK_SESSION_ID = os.getenv("TIKTOK_SESSION_ID")


# ── Core logic ───────────────────────────────────────────────
async def get_followings_via_ui(username: str, limit: int = 100) -> list[str]:
    """Fetch followings by clicking 'Following' and scrolling the modal."""
    print(f"[*] Fetching followings for @{username} via UI (limit {limit})…")

    if not TIKTOK_SESSION_ID:
        print("[!] WARNING: No TIKTOK_SESSION_ID. Setup might fail if profile is private.")

    found: set[str] = set()
    
    async with async_playwright() as p:
        # Launch headed so user can solve CAPTCHA
        print("[*] Launching browser (HEADED mode)...")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Set viewport to a standard desktop size
            viewport={"width": 1280, "height": 800}
        )

        if TIKTOK_SESSION_ID:
            await context.add_cookies([{
                "name": "sessionid",
                "value": TIKTOK_SESSION_ID,
                "domain": ".tiktok.com",
                "path": "/"
            }])
            print("[*] Injected session cookie.")

        page = await context.new_page()

        try:
            print(f"[*] Navigating to @{username}...")
            await page.goto(f"https://www.tiktok.com/@{username}", wait_until="domcontentloaded", timeout=60000)
            
            print("\n" + "=" * 60)
            print("MANUAL INTERACTION REQUIRED")
            print("1. If a CAPTCHA appears, solve it.")
            print("2. Log in if necessary (should be auto-logged in with cookie).")
            print("3. Click 'Following' on the profile page.")
            print("4. Scroll down the popup list until you have loaded enough users.")
            print(f"   (Target: {limit} users)")
            print("5. Return here and press ENTER to scrape the list.")
            print("=" * 60 + "\n")
            
            input("Press ENTER when you have scrolled the list...")

            print("[*] Scraping loaded users...")
            
            # Scrape all visible user cards
            # Common selectors for user links in following list
            # Usually: <a href="/@username">...</a> or specific data-e2e tags
            
            # We will use a broad strategy to get all user links from the modal
            # The modal often has a class like 'css-1z070wx-DivUserListContainer' but dynamic classes change.
            # We'll look for any link that matches /@username pattern inside the dialog
            
            user_elements = await page.query_selector_all('a[href^="/@"]')
            
            print(f"[*] Found {len(user_elements)} potential user links. Filtering...")
            
            for el in user_elements:
                href = await el.get_attribute("href")
                if href:
                    # href is like /@username
                    u = href.split("@")[-1].split("?")[0].strip('/')
                    # Basic validation to avoid junk
                    if u and u != username and len(u) > 1:
                        found.add(u)
                        if len(found) % 10 == 0:
                            print(f"    Found {len(found)} unique users...")
            
            if len(found) < 5:
                # Fallback: Try looking for text in user-card-nickname elements if links failed
                print("[!] Low count from links. Trying alternative selector...")
                nicknames = await page.query_selector_all('[data-e2e="user-card-nickname"]')
                for el in nicknames:
                    text = await el.text_content()
                    if text:
                        found.add(text.strip())

        except Exception as e:
            print(f"[!] Error: {e}")
            await page.screenshot(path="error_scrape.png")
        finally:
            await browser.close()

    return list(found)




def save_to_users_file(new_users: list[str]) -> int:
    """Append new_users to users.txt, skipping duplicates."""
    existing: set[str] = set()
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            existing = {
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            }

    added = 0
    with open(USERS_FILE, "a", encoding="utf-8") as f:
        # Check if we need a newline first
        if os.path.exists(USERS_FILE) and os.path.getsize(USERS_FILE) > 0:
             # simple check
             pass

        for u in new_users:
            if u not in existing:
                f.write(u + "\n")
                existing.add(u)
                added += 1
    return added


# ── CLI ──────────────────────────────────────────────────────
async def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_followings.py <username> [limit]")
        return

    username = sys.argv[1].lstrip("@")
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    users = await get_followings_via_ui(username, limit)

    if users:
        added = save_to_users_file(users)
        print(f"\n[+] Total unique followings found: {len(users)}")
        print(f"[+] Added {added} new usernames to users.txt")
    else:
        print("\n[-] No followings found.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt: pass
