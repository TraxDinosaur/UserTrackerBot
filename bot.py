import os
import json
from pymongo import MongoClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGODB_URI = os.getenv('MONGOURI')
ADMIN_ID = int(os.getenv("ADMIN_ID"))

MONGO_DB = False   # set True to use MongoDB
LOCAL = True       # set True to use local JSON

# Ensure only one is True
if MONGO_DB and LOCAL:
    raise ValueError("Only one of MONGO_DB or LOCAL can be True!")

if MONGO_DB:
    client = MongoClient(MONGODB_URI)
    db = client["telegram_bot"]
    users_collection = db["users"]

elif LOCAL:
    DATA_FILE = "users.json"
    try:
        with open(DATA_FILE, "r") as f:
            local_data = json.load(f)
    except FileNotFoundError:
        local_data = {"users": []}


def save_user(user_id: int, username: str, full_name: str):
    if MONGO_DB:
        if not users_collection.find_one({"id": user_id}):
            users_collection.insert_one({
                "id": user_id,
                "username": username,
                "full_name": full_name
            })
    elif LOCAL:
        if not any(u["id"] == user_id for u in local_data["users"]):
            local_data["users"].append({
                "id": user_id,
                "username": username,
                "full_name": full_name
            })
            with open(DATA_FILE, "w") as f:
                json.dump(local_data, f, indent=4)


def get_all_users():
    if MONGO_DB:
        return list(users_collection.find())
    elif LOCAL:
        return local_data["users"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.username, user.full_name)
    await update.message.reply_text("Heyy You Come On, Subscribe TraxDinosaur")


async def user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"Your Telegram ID: {user.id}")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("Come back Tomorrow to use this command.")

    users = get_all_users()
    await update.message.reply_text(f"Total Users: {len(users)}")


async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("Come back next Month to use this command.")

    users = get_all_users()
    if not users:
        await update.message.reply_text("No users found.")
    else:
        msg = "Users List:\n"
        for u in users:
            msg += f"- {u.get('full_name')} (@{u.get('username')}) | ID: {u.get('id')}\n"
        await update.message.reply_text(msg)


def main():
    print("Subscribed TraxDinosaur Or Not?\nBTW Bot Is Running....\n")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", user_id))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("users", users_list))

    application.run_polling()


if __name__ == "__main__":
    main()
