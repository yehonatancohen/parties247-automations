import os
import requests

def main():
    target_dir = os.path.join("auto_content", "assets", "fonts")
    target_path = os.path.join(target_dir, "Rubik-Bold.ttf")
    os.makedirs(target_dir, exist_ok=True)
    
    # Potential URLs for the STATIC Bold version
    urls = [
        "https://raw.githubusercontent.com/googlefonts/rubik/master/fonts/ttf/Rubik-Bold.ttf",
        "https://raw.githubusercontent.com/googlefonts/rubik/main/fonts/ttf/Rubik-Bold.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/rubik/static/Rubik-Bold.ttf", 
        "https://github.com/google/fonts/raw/main/ofl/rubik/static/Rubik-Bold.ttf"
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0'}

    print("🕵️  Hunting for the elusive Static Rubik Bold...")

    for url in urls:
        print(f"👉 Checking: {url}")
        try:
            # Head request first to check existence and size
            r = requests.get(url, headers=headers, stream=True)
            if r.status_code == 200:
                content = r.content
                size = len(content)
                print(f"   ✅ Found! Size: {size} bytes")
                
                # Heuristic: Static Bold is usually < 200KB. Variable is > 300KB.
                if size > 300000:
                    print("   ⚠️  Warning: This looks like the Variable Font (too big). Skipping...")
                    continue
                
                with open(target_path, 'wb') as f:
                    f.write(content)
                print(f"🎉 SUCCESS! Saved correct static font to {target_path}")
                print("➡️  Please run 'debug_in_docker.bat' again to verify.")
                return
            else:
                print(f"   ❌ 404/Fail ({r.status_code})")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    print("❌ Could not find a suitable static font file online.")
    print("👉 Solution: Please manually download 'Rubik-Bold.ttf' (Static) from Google Fonts website and place it in 'auto_content/assets/fonts/'.")

if __name__ == "__main__":
    main()
