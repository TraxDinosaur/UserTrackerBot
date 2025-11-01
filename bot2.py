import os
import json
import asyncio
import time
from pymongo import MongoClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden
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

# Broadcast status tracking
broadcast_status = {
    "is_running": False,
    "current_progress": 0,
    "total_users": 0,
    "successful": 0,
    "failed": 0,
    "start_time": 0
}


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


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized to use this command.")

    if not context.args:
        return await update.message.reply_text(
            "📢 **Broadcast Usage:**\n"
            "`/broadcast your message here`\n\n"
            "💡 **Pro Tip:** You can use formatting:\n"
            "- *bold* text\n"
            "- _italic_ text\n"
            "- `code` text\n"
            "- [link](url) format"
        )

    if broadcast_status["is_running"]:
        return await update.message.reply_text("⚠️ A broadcast is already in progress. Please wait for it to complete.")

    # Get the broadcast message
    broadcast_message = " ".join(context.args)
    
    # Get all users
    users = get_all_users()
    total_users = len(users)
    
    if total_users == 0:
        return await update.message.reply_text("❌ No users found to broadcast.")
    
    # Initialize broadcast status
    broadcast_status.update({
        "is_running": True,
        "current_progress": 0,
        "total_users": total_users,
        "successful": 0,
        "failed": 0,
        "start_time": time.time()
    })
    
    # Send initial confirmation
    initial_msg = await update.message.reply_text(
        f"🚀 **Starting Broadcast**\n"
        f"📊 Total Users: {total_users}\n"
        f"⏳ Preparing to send...\n\n"
        f"📨 **Message Preview:**\n{broadcast_message[:200]}..."
    )
    
    # Send broadcast to all users
    successful = 0
    failed = 0
    failed_users = []
    
    for index, user in enumerate(users, 1):
        if not broadcast_status["is_running"]:
            break
            
        user_id = user["id"]
        
        try:
            # Try to send the message
            await context.bot.send_message(
                chat_id=user_id,
                text=broadcast_message,
                parse_mode='Markdown'
            )
            successful += 1
            
            # Update progress every 10 users or for the last user
            if index % 10 == 0 or index == total_users:
                progress = (index / total_users) * 100
                elapsed_time = time.time() - broadcast_status["start_time"]
                
                try:
                    await initial_msg.edit_text(
                        f"📤 **Broadcast in Progress**\n"
                        f"📊 Progress: {index}/{total_users} ({progress:.1f}%)\n"
                        f"✅ Successful: {successful}\n"
                        f"❌ Failed: {failed}\n"
                        f"⏱️ Elapsed: {elapsed_time:.1f}s\n"
                        f"📨 **Message:** {broadcast_message[:100]}..."
                    )
                except:
                    pass
            
        except (BadRequest, Forbidden) as e:
            # User blocked the bot or chat doesn't exist
            failed += 1
            failed_users.append({
                "id": user_id,
                "username": user.get("username", "N/A"),
                "full_name": user.get("full_name", "N/A"),
                "error": str(e)
            })
        except TelegramError as e:
            # Other Telegram errors
            failed += 1
            failed_users.append({
                "id": user_id,
                "username": user.get("username", "N/A"),
                "full_name": user.get("full_name", "N/A"),
                "error": str(e)
            })
        except Exception as e:
            # Any other unexpected errors
            failed += 1
            failed_users.append({
                "id": user_id,
                "username": user.get("username", "N/A"),
                "full_name": user.get("full_name", "N/A"),
                "error": "Unknown error"
            })
        
        # Small delay to avoid hitting rate limits
        await asyncio.sleep(0.1)
    
    # Calculate final statistics
    total_time = time.time() - broadcast_status["start_time"]
    
    # Prepare final report
    report = (
        f"🎉 **Broadcast Completed!**\n\n"
        f"📊 **Statistics:**\n"
        f"• ✅ Successful: {successful}\n"
        f"• ❌ Failed: {failed}\n"
        f"• 📨 Total: {total_users}\n"
        f"• ⏱️ Time Taken: {total_time:.1f}s\n"
        f"• 📈 Success Rate: {(successful/total_users)*100:.1f}%\n\n"
    )
    
    # Add failed users details if any
    if failed_users:
        report += f"📋 **Failed Users ({failed}):**\n"
        for i, failed_user in enumerate(failed_users[:10], 1):  # Show first 10 failed users
            report += f"{i}. {failed_user['full_name']} (@{failed_user['username']})\n"
        
        if failed > 10:
            report += f"... and {failed - 10} more users\n"
    
    # Send final report
    await initial_msg.edit_text(report)
    
    # Reset broadcast status
    broadcast_status.update({
        "is_running": False,
        "current_progress": 0,
        "total_users": 0,
        "successful": 0,
        "failed": 0,
        "start_time": 0
    })


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized to use this command.")
    
    if not broadcast_status["is_running"]:
        return await update.message.reply_text("ℹ️ No broadcast is currently running.")
    
    broadcast_status["is_running"] = False
    await update.message.reply_text("🛑 Broadcast cancelled successfully.")


async def broadcast_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized to use this command.")
    
    if not broadcast_status["is_running"]:
        return await update.message.reply_text("ℹ️ No broadcast is currently running.")
    
    current = broadcast_status["current_progress"]
    total = broadcast_status["total_users"]
    successful = broadcast_status["successful"]
    failed = broadcast_status["failed"]
    elapsed = time.time() - broadcast_status["start_time"]
    progress = (current / total) * 100 if total > 0 else 0
    
    status_msg = (
        f"📤 **Broadcast Status**\n\n"
        f"📊 Progress: {current}/{total} ({progress:.1f}%)\n"
        f"✅ Successful: {successful}\n"
        f"❌ Failed: {failed}\n"
        f"⏱️ Elapsed Time: {elapsed:.1f}s\n"
        f"🚀 Status: Running...\n\n"
        f"Use /bcancel to stop the broadcast."
    )
    
    await update.message.reply_text(status_msg)


def main():
    print("Subscribed TraxDinosaur Or Not?\nBTW Bot Is Running....\n")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", user_id))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("users", users_list))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("bcancel", broadcast_cancel))
    application.add_handler(CommandHandler("bstatus", broadcast_status_cmd))

    application.run_polling()


if __name__ == "__main__":
    main()
