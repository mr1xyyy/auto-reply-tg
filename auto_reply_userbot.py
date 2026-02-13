"""
Telegram userbot auto-replier using Telethon.

Features:
- Replies only when account is "offline" (no activity for 3+ minutes).
- Skips users in blacklist.json.
- Picks random reply templates from replies.txt.
- Sends only one auto-reply per user (tracked in replied.json).

Run:
    python auto_reply_userbot.py

Environment variables (recommended):
    API_ID=<your_api_id>
    API_HASH=<your_api_hash>

Optional constants fallback is also supported below.
"""

import asyncio
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import List, Set

from telethon import TelegramClient, events

# ------------------------------
# Configuration
# ------------------------------

# Read credentials from environment variables first.
# If env vars are not set, script falls back to constants below.
API_ID = int(os.getenv("API_ID", "0")) or 0
API_HASH = os.getenv("API_HASH", "")

# Optional constant fallback if you don't want to use env variables.
# Example:
# API_ID_FALLBACK = 123456
# API_HASH_FALLBACK = "0123456789abcdef0123456789abcdef"
API_ID_FALLBACK = 0
API_HASH_FALLBACK = ""

# Telethon session file name.
SESSION_NAME = "auto_reply_userbot"

# Paths for data files.
BLACKLIST_PATH = Path("blacklist.json")
REPLIES_PATH = Path("replies.txt")
REPLIED_PATH = Path("replied.json")

# User is considered "offline" if there was no activity for this many seconds.
OFFLINE_THRESHOLD_SECONDS = 3 * 60

# ------------------------------
# Runtime state
# ------------------------------

# Timestamp of the latest activity detected by this client.
last_activity_ts = time.time()

# In-memory caches loaded from files.
blacklist_user_ids: Set[int] = set()
replied_user_ids: Set[int] = set()
replies_pool: List[str] = []


# ------------------------------
# File helpers
# ------------------------------

def load_blacklist(path: Path) -> Set[int]:
    """Load blacklist IDs from JSON file. Returns an empty set if missing/invalid."""
    if not path.exists():
        logging.warning("%s not found. Using empty blacklist.", path)
        return set()

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            logging.warning("%s should contain a JSON list. Using empty blacklist.", path)
            return set()

        return {int(user_id) for user_id in data}
    except Exception as exc:
        logging.warning("Failed to read %s (%s). Using empty blacklist.", path, exc)
        return set()


def load_replied(path: Path) -> Set[int]:
    """Load already-replied user IDs from JSON file. Creates file if missing."""
    if not path.exists():
        # Initialize with an empty array so future runs can persist state.
        save_replied(path, set())
        return set()

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            logging.warning("%s should contain a JSON list. Resetting replied data.", path)
            save_replied(path, set())
            return set()

        return {int(user_id) for user_id in data}
    except Exception as exc:
        logging.warning("Failed to read %s (%s). Resetting replied data.", path, exc)
        save_replied(path, set())
        return set()


def save_replied(path: Path, replied_ids: Set[int]) -> None:
    """Persist replied user IDs to disk as a JSON list."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(sorted(replied_ids), f, indent=2)


def load_replies(path: Path) -> List[str]:
    """Load dynamic replies from text file (one reply per non-empty line)."""
    if not path.exists():
        logging.warning("%s not found. Creating with a default reply.", path)
        path.write_text("I'm currently away. I'll get back to you soon.\n", encoding="utf-8")

    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    replies = [line for line in lines if line]

    if not replies:
        # Guarantee at least one reply to avoid random.choice errors.
        replies = ["I'm currently away. I'll get back to you soon."]

    return replies


# ------------------------------
# Activity tracking
# ------------------------------

def mark_activity(reason: str) -> None:
    """Update activity timestamp whenever user/account activity is detected."""
    global last_activity_ts
    last_activity_ts = time.time()
    logging.debug("Activity updated (%s) at %s", reason, last_activity_ts)


def is_offline() -> bool:
    """Check if account is considered offline based on inactivity time window."""
    return (time.time() - last_activity_ts) >= OFFLINE_THRESHOLD_SECONDS


# ------------------------------
# Main bot logic
# ------------------------------

async def main() -> None:
    """Entrypoint for running the Telethon userbot."""
    global blacklist_user_ids, replied_user_ids, replies_pool

    # Resolve credentials with env-first and constant fallback strategy.
    api_id = API_ID if API_ID else API_ID_FALLBACK
    api_hash = API_HASH if API_HASH else API_HASH_FALLBACK

    if not api_id or not api_hash:
        raise RuntimeError(
            "Missing Telegram credentials. Set API_ID and API_HASH environment variables "
            "or update API_ID_FALLBACK/API_HASH_FALLBACK constants."
        )

    # Load all data files once at startup.
    blacklist_user_ids = load_blacklist(BLACKLIST_PATH)
    replied_user_ids = load_replied(REPLIED_PATH)
    replies_pool = load_replies(REPLIES_PATH)

    client = TelegramClient(SESSION_NAME, api_id, api_hash)

    # Track outgoing messages as activity (indicates user/account is active).
    @client.on(events.NewMessage(outgoing=True))
    async def on_outgoing_message(_event):
        mark_activity("outgoing message")

    # Track read acknowledgements as another signal of activity.
    @client.on(events.MessageRead(outbox=True))
    async def on_message_read(_event):
        mark_activity("message read")

    # Auto-reply only to new incoming private messages.
    @client.on(events.NewMessage(incoming=True))
    async def on_incoming_private_message(event):
        # Ignore non-private chats (groups/channels).
        if not event.is_private:
            return

        sender = await event.get_sender()
        sender_id = int(sender.id)

        # Skip blacklisted users.
        if sender_id in blacklist_user_ids:
            logging.info("Skipping blacklisted user: %s", sender_id)
            return

        # Only one automatic reply per user.
        if sender_id in replied_user_ids:
            logging.info("Already auto-replied to user %s. Skipping.", sender_id)
            return

        # Reply only when account has been inactive for 3+ minutes.
        if not is_offline():
            logging.info("User is active. Not sending auto-reply to %s.", sender_id)
            return

        # Pick random reply line from replies.txt.
        reply_text = random.choice(replies_pool)

        await event.reply(reply_text)
        logging.info("Sent auto-reply to user %s", sender_id)

        # Persist one-time reply state.
        replied_user_ids.add(sender_id)
        save_replied(REPLIED_PATH, replied_user_ids)

        # Sending a message counts as account activity.
        mark_activity("auto-reply sent")

    # Connect and run until manually stopped.
    await client.start()
    logging.info("Userbot started. Listening for private messages...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    # Basic log configuration for terminal usage (CMD/PowerShell/Linux).
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Userbot stopped by user.")
