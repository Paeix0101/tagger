import os
import json
import requests
from flask import Flask, request

# =================== CONFIG =================== #
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))
BOT_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)

# =================== HELPERS =================== #
def send_message(chat_id, text, parse_mode=None):
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
        data["disable_web_page_preview"] = True
    requests.post(f"{BOT_API}/sendMessage", json=data)

def get_chat_administrators(chat_id):
    resp = requests.get(f"{BOT_API}/getChatAdministrators?chat_id={chat_id}")
    if resp.ok:
        return resp.json().get("result", [])
    return []

def save_member(chat_id, user_id, first_name, username=None):
    """Save members per group for tagging later"""
    filename = f"members_{chat_id}.txt"
    if not os.path.exists(filename):
        open(filename, "w").close()
    with open(filename, "r") as f:
        members = f.read().splitlines()
    if str(user_id) not in [m.split("|")[0] for m in members]:
        with open(filename, "a") as f:
            f.write(f"{user_id}|{first_name}|{username or ''}\n")

def load_members(chat_id):
    filename = f"members_{chat_id}.txt"
    if not os.path.exists(filename):
        return []
    with open(filename, "r") as f:
        members = [line.strip().split("|") for line in f.readlines()]
    return members  # list of [id, first_name, username]

def split_mentions(mentions, max_len=4000):
    """Split mention text into chunks within Telegram’s limit"""
    chunks, current = [], ""
    for mention in mentions:
        if len(current) + len(mention) + 1 > max_len:
            chunks.append(current)
            current = mention
        else:
            current += " " + mention if current else mention
    if current:
        chunks.append(current)
    return chunks

# =================== WEBHOOK =================== #
@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        return "Bot is running ✅"

    update = request.get_json()
    msg = update.get("message") or update.get("channel_post")
    my_chat_member = update.get("my_chat_member")

    # Track members when they talk
    if msg:
        chat_id = msg["chat"]["id"]
        from_user = msg.get("from", {})
        if str(chat_id).startswith("-") and from_user.get("id"):
            save_member(chat_id, from_user["id"], from_user.get("first_name", "User"), from_user.get("username"))

    # =================== /runtag =================== #
    if msg and "reply_to_message" in msg and msg.get("text", "").lower().startswith("/runtag"):
        chat_id = msg["chat"]["id"]
        from_user = msg.get("from", {})

        # Check admin
        admins = [a["user"]["id"] for a in get_chat_administrators(chat_id)]
        is_admin = from_user["id"] in admins if from_user else False

        if not is_admin:
            send_message(chat_id, "⚠️ Only admins can use /runtag")
            return "OK"

        replied_msg = msg["reply_to_message"]

        # Load members
        members = load_members(chat_id)
        if not members:
            send_message(chat_id, "❌ No members tracked yet. Bot only knows those who have spoken.")
            return "OK"

        # Build mentions
        mention_list = []
        for uid, first, uname in members:
            if uname:
                mention_list.append(f"@{uname}")
            else:
                mention_list.append(f"<a href='tg://user?id={uid}'>{first}</a>")

        # Copy the replied message
        requests.post(f"{BOT_API}/copyMessage", json={
            "chat_id": chat_id,
            "from_chat_id": chat_id,
            "message_id": replied_msg["message_id"]
        })

        # Send mentions in chunks
        chunks = split_mentions(mention_list)
        for chunk in chunks:
            send_message(chat_id, f"📢 {chunk}", parse_mode="HTML")

        return "OK"

    return "OK"

# =================== RUN =================== #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))