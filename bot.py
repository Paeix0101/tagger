import os
import re
import requests
import yt_dlp
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Render pe Environment Variable me set karna
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_URL = f"https://api.telegram.org/file/bot{BOT_TOKEN}/"

app = Flask(__name__)

# ✅ Home route (to check service is live)
@app.route("/", methods=["GET"])
def home():
    return "✅ Telegram Bot is running on Render!"

# ✅ Webhook route
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json()
    if not update:
        return {"ok": False}

    print("📩 Update received:", update)  # Debugging logs

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        # Reply to /start
        if text == "/start":
            send_message(chat_id, "Hello 👋 I can download YouTube & Instagram videos. Just send me a link!")
        elif is_youtube_url(text) or is_instagram_url(text):
            send_message(chat_id, "⏳ Downloading your video, please wait...")
            download_and_send(chat_id, text)
        else:
            send_message(chat_id, f"You said: {text}")

    return {"ok": True}

# ✅ Check if message is YouTube link
def is_youtube_url(url):
    youtube_regex = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
    return re.match(youtube_regex, url)

# ✅ Check if message is Instagram link
def is_instagram_url(url):
    insta_regex = r"(https?://)?(www\.)?instagram\.com/(reel|p|tv)/.+"
    return re.match(insta_regex, url)

# ✅ Download video using yt-dlp and send to Telegram
def download_and_send(chat_id, url):
    try:
        ydl_opts = {
            "format": "mp4",
            "outtmpl": "/tmp/video.%(ext)s",  # save in temp folder
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        # ✅ Send as video file
        send_video(chat_id, file_path)

        # ✅ remove file after sending
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        print("❌ Error downloading:", e)
        send_message(chat_id, "❌ Failed to download video. Try another link.")

# ✅ Helper function to send text messages
def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("❌ Error sending message:", e)

# ✅ Helper function to send video files
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