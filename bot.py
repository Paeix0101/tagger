import os
from flask import Flask, request
from telegram import Bot, Update

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)

MEMBERS_FILE = "members.txt"

# Load allowed groups
with open("groups.txt") as f:
    ALLOWED_GROUPS = [line.strip() for line in f if line.strip()]

app = Flask(__name__)

# Save members whenever they send a message
def save_member(user):
    if user.is_bot:
        return
    with open(MEMBERS_FILE, "a+") as f:
        f.seek(0)
        members = {line.strip() for line in f}
        if str(user.id) not in members:
            f.write(str(user.id) + "\n")

# Command: /runtag
def runtag(update: Update):
    chat = update.effective_chat
    user = update.effective_user

    # Only allowed groups
    if str(chat.id) not in ALLOWED_GROUPS:
        return

    # Only admins/owner can use
    member = bot.get_chat_member(chat.id, user.id)
    if member.status not in ["administrator", "creator"]:
        update.message.reply_text("❌ Only admins can use this command.")
        return

    # Must reply to a message
    if not update.message.reply_to_message:
        update.message.reply_text("Reply to a message with /runtag to tag everyone.")
        return

    replied = update.message.reply_to_message

    # Load stored members
    try:
        with open(MEMBERS_FILE) as f:
            user_ids = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        user_ids = []

    if not user_ids:
        update.message.reply_text("⚠️ No members stored yet. They need to send messages first.")
        return

    # Build mentions
    tags = []
    for uid in user_ids:
        try:
            u = bot.get_chat_member(chat.id, int(uid)).user
            tags.append(u.mention_html())
        except:
            continue

    # Use replied text or caption
    if replied.text:
        original_text = replied.text_html
    elif replied.caption:
        original_text = replied.caption_html
    else:
        original_text = "📷 Media"

    # Send one message: original + mentions
    bot.send_message(
        chat_id=chat.id,
        text=f"{original_text}\n\n{' '.join(tags)}",
        parse_mode="HTML"
    )

# Flask webhook
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)

    # Save members whenever they send messages
    if update.message and update.message.from_user:
        save_member(update.message.from_user)

    # Run /runtag
    if update.message and update.message.text and update.message.text.startswith("/runtag"):
        runtag(update)

    return "ok"

@app.route("/")
def home():
    return "Bot is running ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))