import os
import re
import requests
from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-service.onrender.com
BOT_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)

# --------------------- helpers --------------------- #
YDL_OPTS_COMMON = {
    "quiet": True,
    "nocheckcertificate": True,
    "noplaylist": True,
    "skip_download": True,
    # Progressive MP4 (video+audio) to avoid ffmpeg merge
    "format": "best[ext=mp4][vcodec!=none][acodec!=none]/best",
    "extract_flat": False,
}

INSTAGRAM_PAT = re.compile(r"(https?://)?(www\.)?instagram\.com/(p|reel|tv)/[A-Za-z0-9_\-]+")
YOUTUBE_PAT = re.compile(r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_\-]+")

def send_message(chat_id, text, parse_mode=None):
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
        data["disable_web_page_preview"] = True
    requests.post(f"{BOT_API}/sendMessage", json=data, timeout=20)

def send_video(chat_id, video_url, caption=None):
    data = {"chat_id": chat_id, "video": video_url}
    if caption:
        data["caption"] = caption[:1024]
    requests.post(f"{BOT_API}/sendVideo", json=data, timeout=60)

def send_photo(chat_id, photo_url, caption=None):
    data = {"chat_id": chat_id, "photo": photo_url}
    if caption:
        data["caption"] = caption[:1024]
    requests.post(f"{BOT_API}/sendPhoto", json=data, timeout=60)

def extract_medias(url: str):
    """
    Returns a list of dicts: [{"type": "video"|"photo", "url": "...", "caption": "..."}]
    Uses yt-dlp to get direct media URLs so Telegram can fetch them.
    """
    medias = []
    with YoutubeDL(YDL_OPTS_COMMON) as ydl:
        info = ydl.extract_info(url, download=False)

    # If playlist/album of multiple entries (IG carousel etc.)
    if isinstance(info, dict) and info.get("_type") == "playlist" and "entries" in info:
        entries = info["entries"] or []
    else:
        entries = [info]

    for it in entries:
        if not isinstance(it, dict):
            continue

        # Try to choose a direct URL
        direct_url = it.get("url")
        ext = (it.get("ext") or "").lower()
        vcodec = it.get("vcodec")
        acodec = it.get("acodec")
        thumbnails = it.get("thumbnails") or []
        title = it.get("title") or ""
        desc = it.get("description") or ""
        caption = title if title else (desc[:200] if desc else "")

        # Heuristic: video if we have both codecs or ext is mp4/webm
        is_video = (vcodec and vcodec != "none") or ext in {"mp4", "webm", "m4v"}

        if direct_url and is_video:
            medias.append({"type": "video", "url": direct_url, "caption": caption})
            continue

        # If not video, try to pick a high-res thumbnail/photo
        photo_url = None
        if thumbnails:
            # pick the largest thumbnail by width/height if present
            sorted_thumbs = sorted(
                thumbnails,
                key=lambda t: (t.get("height") or 0) * (t.get("width") or 0),
                reverse=True,
            )
            if sorted_thumbs and sorted_thumbs[0].get("url"):
                photo_url = sorted_thumbs[0]["url"]

        # Instagram images often provide direct 'url' with ext=jpg
        if not photo_url and direct_url and (ext in {"jpg", "jpeg", "png"}):
            photo_url = direct_url

        if photo_url:
            medias.append({"type": "photo", "url": photo_url, "caption": caption})

    return medias

def is_instagram(url: str) -> bool:
    return bool(INSTAGRAM_PAT.search(url))

def is_youtube(url: str) -> bool:
    return bool(YOUTUBE_PAT.search(url))

def find_url_in_text(text: str) -> str | None:
    if not text:
        return None
    # quick url pick (first http(s)://... )
    m = re.search(r"https?://[^\s]+", text)
    return m.group(0) if m else None

# --------------------- webhook --------------------- #
@app.route("/", methods=["GET"])
def home():
    return "IG/YT fetch bot running ✅"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True, silent=True) or {}
    msg = update.get("message") or update.get("channel_post")
    if not msg:
        return jsonify(ok=True)

    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    is_private = chat.get("type") == "private"
    text = msg.get("text") or msg.get("caption") or ""

    # Only serve in DM; if used in group, ask user to DM the bot
    if not is_private:
        # try to DM the sender if they have /start-ed the bot
        user = msg.get("from") or {}
        uid = user.get("id")
        if uid:
            send_message(uid, "👋 Link mujhe **DM** me bhejo. Main yahin aapko media bhej dunga.")
        return jsonify(ok=True)

    if text.strip().lower().startswith("/start"):
        send_message(
            chat_id,
            "Send me an Instagram **post/reel** or YouTube **video** link.\n"
            "I’ll try to send the video/image directly here. 🔗➡️🎥🖼️"
        )
        return jsonify(ok=True)

    url = find_url_in_text(text)
    if not url:
        send_message(chat_id, "Please send an Instagram/YouTube link.")
        return jsonify(ok=True)

    if not (is_instagram(url) or is_youtube(url)):
        send_message(chat_id, "I currently support Instagram posts/reels and YouTube videos only.")
        return jsonify(ok=True)

    try:
        medias = extract_medias(url)
        if not medias:
            send_message(chat_id, "Sorry, couldn’t fetch media for that link.")
            return jsonify(ok=True)

        # Send each media item; keep it simple
        sent_any = False
        for m in medias:
            if m["type"] == "video":
                send_video(chat_id, m["url"], caption=m.get("caption"))
                sent_any = True
            elif m["type"] == "photo":
                send_photo(chat_id, m["url"], caption=m.get("caption"))
                sent_any = True

        if not sent_any:
            send_message(chat_id, "I found something, but couldn’t send it. It may be restricted.")
    except Exception as e:
        # Most common causes: private/protected content, region locks, or site changes
        send_message(
            chat_id,
            "Fetch failed. Possible reasons:\n"
            "• Private/protected content\n"
            "• Region-locked / age-restricted\n"
            "• Site changed layout\n\n"
            f"Error: {type(e).__name__}"
        )

    return jsonify(ok=True)

# --------------------- run locally / set webhook --------------------- #
if __name__ == "__main__":
    # Optional: auto-set webhook if WEBHOOK_URL provided
    if WEBHOOK_URL and BOT_TOKEN:
        try:
            requests.get(
                f"{BOT_API}/setWebhook",
                params={"url": f"{WEBHOOK_URL}/webhook"},
                timeout=10
            )
        except Exception:
            pass

    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)