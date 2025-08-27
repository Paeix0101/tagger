import os
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
from telegram.error import Forbidden

# Load BOT TOKEN
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)

# Load allowed groups from groups.txt
with open("groups.txt") as f:
    ALLOWED_GROUPS = [line.strip() for line in f if line.strip()]

app = Flask(__name__)

# Command: /runtag
def runtag(update: Update, context):
    chat = update.effective_chat
    user = update.effective_user

    # Check if group is allowed
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

    # Try fetching members (works if group < 200, Telegram API restriction)
    try:
        members = bot.get_chat_administrators(chat.id)
        tags = " ".join([m.user.mention_html() for m in members])
    except Forbidden:
        update.message.reply_text("⚠️ Cannot fetch all members in large groups.")
        return

    # Send tagging message
    bot.send_message(
        chat_id=chat.id,
        text=f"{replied.text_html or '📷 Media/Content'}\n\n{tags}",
        parse_mode="HTML"
    )

# Flask route for webhook
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dp = Dispatcher(bot, None, workers=0)
    dp.add_handler(CommandHandler("runtag", runtag))
    dp.process_update(update)
    return "ok"

@app.route("/")
def home():
    return "Bot is running ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))