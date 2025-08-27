import os
import re
import requests
import yt_dlp
from flask import Flask, request

# ✅ Environment variable for Telegram bot
BOT_TOKEN = os.getenv("BOT_TOKEN")  
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)

# ✅ Home route
@app.route("/", methods=["GET"])
def home():
    return "✅ Telegram Bot is running on Render!"

# ✅ Webhook route
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json()
    if not update:
        return {"ok": False}

    print("📩 Update received:", update)

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/start":
            send_message(chat_id, "👋 Hello! Send me a YouTube or Instagram link and I'll download it for you.")
        elif is_youtube_url(text) or is_instagram_url(text):
            send_message(chat_id, "⏳ Downloading your video, please wait...")
            download_and_send(chat_id, text)
        else:
            send_message(chat_id, f"You said: {text}")

    return {"ok": True}

# ✅ YouTube regex
def is_youtube_url(url):
    youtube_regex = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
    return re.match(youtube_regex, url)

# ✅ Instagram regex
def is_instagram_url(url):
    insta_regex = r"(https?://)?(www\.)?instagram\.com/(reel|p|tv)/.+"
    return re.match(insta_regex, url)

# ✅ Download & send video
def download_and_send(chat_id, url):
    try:
        ydl_opts = {
            "format": "best",   # get best quality available
            "outtmpl": "/tmp/video.%(ext)s",
            "quiet": True,
            "noplaylist": True,
        }

        # ✅ Optional: use cookies.txt if available (for YouTube)
        cookies_path = "/etc/cookies.txt"  # Upload this file in Render if needed
        if os.path.exists(cookies_path):
            ydl_opts["cookiefile"] = cookies_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        # ✅ Send video
        send_video(chat_id, file_path)

        # ✅ Clean up
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        print("❌ Error downloading:", e)
        send_message(chat_id, "❌ Failed to download video. Try another link or check if it needs login.")

# ✅ Send text message
def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("❌ Error sending message:", e)

# ✅ Send video file
def send_video(chat_id, file_path):
    url = f"{BASE_URL}/sendVideo"
    try:
        with open(file_path, "rb") as f:
            files = {"video": f}
            data = {"chat_id": chat_id}
            requests.post(url, data=data, files=files)
    except Exception as e:
        print("❌ Error sending video:", e)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)