import os
from flask import Flask
from threading import Thread
import logging

# השתקת לוגים
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask('')

@app.route('/')
def home():
    return "I'm alive! DigitalOcean Bot is running."

@app.route('/health')
def health():
    return "OK", 200

def run():
    port = int(os.environ.get("PORT", 8080))
    print(f"🌍 Starting Web Server on port {port}...")
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()