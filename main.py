import re
import os
import datetime
import asyncio
import psycopg2
from psycopg2.extras import DictCursor
from cachetools import TTLCache
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatMembersFilter

# 🔹 Credentials from environment
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
DATABASE_URL = os.environ["DATABASE_URL"]

CONFIRMATION_GROUP_ID = int(os.environ["CONFIRMATION_GROUP_ID"])
LOG_GROUP_ID = int(os.environ["LOG_GROUP_ID"])
PUBLIC_GROUP_ID = int(os.environ["PUBLIC_GROUP_ID"])

# 🔹 DB connection
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require", cursor_factory=DictCursor)

# 🔹 Create Table (Run this once)
def create_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            buyer TEXT,
            seller TEXT,
            amount INTEGER,
            admin_id BIGINT,
            admin_name TEXT,
            date TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata'),
            log_message_id BIGINT
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

create_table()

# 🔹 Start Pyrogram Client
app = Client("escrowledger", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

# 🔹 Cache for admin IDs (refreshes every 60 seconds)
admin_cache = TTLCache(maxsize=1, ttl=60)

# 🔹 Function to check if a user is an admin
async def is_admin(client, chat_id, user_id):
    try:
        if chat_id in admin_cache:
            return user_id in admin_cache[chat_id]
        admin_ids = set()
        async for admin in client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
            admin_ids.add(admin.user.id)
        admin_cache[chat_id] = admin_ids
        return user_id in admin_ids
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return False

# 🔹 Function to fetch total escrow amount
def get_total():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM transactions")
    total = cursor.fetchone()[0] or 0
    cursor.close()
    conn.close()
    return total

# 🔹 Function to fetch today's escrow amount (Fixed for IST)
def get_day_total():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(amount)
        FROM transactions
        WHERE DATE(date) = DATE(NOW() AT TIME ZONE 'Asia/Kolkata')
    """)
    day_total = cursor.fetchone()[0] or 0
    cursor.close()
    conn.close()
    return day_total

# 🔹 `/stats` - Show total & daily escrow amount
@app.on_message(filters.command("stats") & (filters.chat(CONFIRMATION_GROUP_ID) | filters.chat(LOG_GROUP_ID) | filters.chat(PUBLIC_GROUP_ID)))
async def stats_command(client, message: Message):
    total = get_total()
    day_total = get_day_total()
    response = (
        f"📊 **Escrow Stats of Project Group**\n\n"
        f"💰 **Total Escrow Amount:** __{total}$__\n\n"
        f"📅 **Daywise Escrow Amount:** __{day_total}$__\n\n"
        f"📊 __Always use @ProjectEscrow for safer transactions!__"
    )
    await message.reply(response)
    await asyncio.sleep(2)
    await message.delete()

# 🔹 `/adminwise` - Show admin-wise escrow totals for today
def get_adminwise_totals():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT admin_name, SUM(amount) FROM transactions
        WHERE DATE(date) = DATE(NOW() AT TIME ZONE 'Asia/Kolkata')
        GROUP BY admin_name
    """)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

@app.on_message(filters.command("adminwise") & (filters.chat(CONFIRMATION_GROUP_ID) | filters.chat(LOG_GROUP_ID) | filters.chat(PUBLIC_GROUP_ID)))
async def adminwise_command(client, message: Message):
    admin_totals = get_adminwise_totals()
    if not admin_totals:
        await message.reply("❌ No escrow transactions found for today.")
        await asyncio.sleep(2)
        await message.delete()
        return
    result = "**👥 Admin-wise Escrow Totals (Today):**\n\n"
    for admin_name, total in admin_totals:
        result += f"🛡️ {admin_name}: {total}$\n"
    await message.reply(result)
    await asyncio.sleep(2)
    await message.delete()

# 🔹 `/add` - Logs a deal (Admin Only)
@app.on_message((filters.chat(CONFIRMATION_GROUP_ID) | filters.chat(LOG_GROUP_ID)) & filters.command("add"))
async def confirm_deal(client, message: Message):
    if not await is_admin(client, CONFIRMATION_GROUP_ID, message.from_user.id):
        await message.reply("🚫 You are not authorized to use this command.")
        return

    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply("❌ Reply to a deal form with `/add`.")
        return

    deal_text = message.reply_to_message.text

    buyer_match = re.search(r"BUYER\s*:\s*@(\w+)", deal_text)
    seller_match = re.search(r"SELLER\s*:\s*@(\w+)", deal_text)
    amount_match = re.search(r"DEAL AMOUNT\s*:\s*(\d+)", deal_text)

    if not (buyer_match and seller_match and amount_match):
        await message.reply("❌ Invalid deal form. Ensure it has Buyer, Seller, and Deal Amount.")
        return

    buyer = buyer_match.group(1)
    seller = seller_match.group(1)
    amount = int(amount_match.group(1))
    admin_name = message.from_user.first_name or "Unknown Admin"
    admin_id = message.from_user.id

    log_message = await app.send_message(LOG_GROUP_ID,
        f"✅ **Deal Confirmed** ✅\n"
        f"👤 **BUYER:** @{buyer}\n"
        f"🔗 **SELLER:** @{seller}\n"
        f"💰 **DEAL AMOUNT:** {amount}$\n"
        f"🛡️ **ESCROWED BY:** {admin_name} | ID: {admin_id}\n"
        f"📅 {datetime.datetime.now().astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime('%Y-%m-%d %H:%M:%S')} IST"
    )

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (buyer, seller, amount, admin_id, admin_name, date, log_message_id)
        VALUES (%s, %s, %s, %s, %s, (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata'), %s)
    """, (buyer, seller, amount, admin_id, admin_name, log_message.id))
    conn.commit()
    cursor.close()
    conn.close()

    await message.reply("✅ Deal confirmed and logged in the database & group!")
    await asyncio.sleep(2)
    await message.delete()

# 🔹 `/minus` - Remove last deal from database & group
@app.on_message((filters.chat(CONFIRMATION_GROUP_ID) | filters.chat(LOG_GROUP_ID)) & filters.command("minus"))
async def remove_deal(client, message: Message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, log_message_id FROM transactions ORDER BY date DESC LIMIT 1")
    last_transaction = cursor.fetchone()

    if last_transaction:
        transaction_id, log_message_id = last_transaction
        cursor.execute("DELETE FROM transactions WHERE id = %s", (transaction_id,))
        conn.commit()
        await app.delete_messages(LOG_GROUP_ID, log_message_id)
        await message.reply("✅ Last deal removed from database & group!")
    else:
        await message.reply("❌ No transactions found.")

    cursor.close()
    conn.close()
    await asyncio.sleep(2)
    await message.delete()

# 🔹 Start Userbot
app.run()