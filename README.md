# Escrowledger 🤖

A Telegram userbot that automates escrow transaction logging for trading groups. Built with Pyrogram, PostgreSQL (Neon.tech), and deployed on Replit.

## What it does

- Admins reply to a deal form with `/add` — the bot parses it, logs it to PostgreSQL, and posts a confirmation to a dedicated log group automatically
- `/stats` — shows total and today's escrow volume
- `/adminwise` — shows per-admin deal breakdown for the day
- `/minus` — removes the last logged deal from DB and log group
- Admin validation is cached with TTL to minimize API calls
- All command messages are auto-deleted after execution to keep groups clean

## Tech Stack

- **Python** — async, event-driven
- **Pyrogram** — Telegram MTProto userbot framework
- **PostgreSQL** — Neon.tech serverless Postgres
- **psycopg2** — database driver
- **cachetools** — TTL-based admin cache
- **Replit** — hosting

## Deal Form Format

For `/add` to work, reply to a message in this exact format:
BUYER : @username
SELLER : @username
DEAL AMOUNT : 100

## Setup

### 1. Telegram API Credentials
- Go to https://my.telegram.org
- Create an app and get your `API_ID` and `API_HASH`

### 2. Session String
Run this once interactively to generate your Pyrogram session string:
```python
from pyrogram import Client

with Client(":memory:", api_id=API_ID, api_hash=API_HASH) as app:
    print(app.export_session_string())
```

### 3. Neon DB
- Create a free project at https://neon.tech
- Copy the connection string
- The bot auto-creates the `transactions` table on first run

### 4. Groups
Create 3 Telegram groups and make the userbot account an admin in all three:
- **Confirmation Group** — where admins log deals
- **Log Group** — where confirmed deals are posted
- **Public Group** — where anyone can check stats

Get group IDs by forwarding a message to @username_to_id_bot.

### 5. Environment Variables
Copy `.env.example` and fill in your values. On Replit, add these as Secrets.

### 6. Run
```bash
pip install -r requirements.txt
python main.py
```

## Project Structure
AutomatedEscrowLedger/
├── main.py              # Core userbot logic
├── requirements.txt     # Dependencies
├── .env.example         # Environment variable template
└── README.md
