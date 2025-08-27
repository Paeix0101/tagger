import os
import requests
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Render pe Environment Variable me set karna
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

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
            send_message(chat_id, "Hello 👋 I am alive on Render!")
        else:
            send_message(chat_id, f"You said: {text}")

    return {"ok": True}


# ✅ Helper function to send messages
def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("❌ Error sending message:", e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)