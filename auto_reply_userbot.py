"""
Telegram userbot auto-replier using Telethon.

Features:
- Replies only when account is "offline" (no activity for 3+ minutes).
- Skips users in blacklist.json.
- Picks random reply templates from replies.txt.
- Limits auto-replies to once per user per hour (tracked in replied.json).
- Supports blacklist management from terminal arguments.

Run:
    python auto_reply_userbot.py

Useful terminal commands:
    python auto_reply_userbot.py --init-files
    python auto_reply_userbot.py --show-blacklist
    python auto_reply_userbot.py --add-blacklist 12345 67890
    python auto_reply_userbot.py --delete-blacklist 12345
    python auto_reply_userbot.py --reset-replied

Environment variables (recommended):
    API_ID=<your_api_id>
    API_HASH=<your_api_hash>

Optional constants fallback is also supported below.
"""

import argparse
import asyncio
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Dict, List, Set

# ------------------------------
# Configuration
# ------------------------------

# Read credentials from environment variables first.
# If env vars are not set, script falls back to constants below.
def parse_api_id(value: str) -> int:
    """Parse API_ID safely; return 0 when value is empty/invalid."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


API_ID = parse_api_id(os.getenv("API_ID", "0")) or 0
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
REPLY_COOLDOWN_SECONDS = 3600

# ------------------------------
# Runtime state
# ------------------------------

# Timestamp of the latest activity detected by this client.
last_activity_ts = time.time()

# In-memory caches loaded from files.
blacklist_user_ids: Set[int] = set()
replied_user_timestamps: Dict[int, int] = {}
replies_pool: List[str] = []


# ------------------------------
# File helpers
# ------------------------------

def save_json_list(path: Path, values: Set[int]) -> None:
    """Save integer IDs as sorted JSON list."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(sorted(values), f, indent=2)


def load_blacklist(path: Path) -> Set[int]:
    """Load blacklist IDs from JSON file. Returns an empty set if missing/invalid."""
    if not path.exists():
        logging.warning("%s not found. Creating empty blacklist.", path)
        save_json_list(path, set())
        return set()

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            logging.warning("%s should contain a JSON list. Resetting to empty list.", path)
            save_json_list(path, set())
            return set()

        return {int(user_id) for user_id in data}
    except Exception as exc:
        logging.warning("Failed to read %s (%s). Resetting to empty blacklist.", path, exc)
        save_json_list(path, set())
        return set()


def load_replied(path: Path) -> Dict[int, int]:
    """Load last auto-reply timestamps from JSON. Supports old list format."""
    if not path.exists():
        save_replied(path, {})
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # New format: {"<user_id>": <unix_ts>}
        if isinstance(data, dict):
            result: Dict[int, int] = {}
            for user_id, ts in data.items():
                try:
                    result[int(user_id)] = int(ts)
                except (TypeError, ValueError):
                    continue
            if len(result) != len(data):
                save_replied(path, result)
            return result

        # Backward compatibility: old format [user_id, ...]
        if isinstance(data, list):
            converted = {int(user_id): 0 for user_id in data}
            save_replied(path, converted)
            return converted

        logging.warning("%s has unsupported format. Resetting replied data.", path)
        save_replied(path, {})
        return {}
    except Exception as exc:
        logging.warning("Failed to read %s (%s). Resetting replied data.", path, exc)
        save_replied(path, {})
        return {}


def save_replied(path: Path, replied_map: Dict[int, int]) -> None:
    """Persist user_id -> last_reply_unix_ts map to disk."""
    payload = {str(user_id): int(ts) for user_id, ts in sorted(replied_map.items())}
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_replies(path: Path) -> List[str]:
    """Load dynamic replies from text file (one reply per non-empty line)."""
    if not path.exists():
        logging.warning("%s not found. Creating with a default reply.", path)
        path.write_text("I'm currently away. I'll get back to you soon.\n", encoding="utf-8")

    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    replies = [line for line in lines if line]

    if not replies:
        replies = ["I'm currently away. I'll get back to you soon."]

    return replies


def ensure_data_files_exist() -> None:
    """Ensure all required local data files exist with safe defaults."""
    if not BLACKLIST_PATH.exists():
        save_json_list(BLACKLIST_PATH, set())
    if not REPLIED_PATH.exists():
        save_replied(REPLIED_PATH, {})
    if not REPLIES_PATH.exists():
        REPLIES_PATH.write_text("I'm currently away. I'll get back to you soon.\n", encoding="utf-8")


# ------------------------------
# CLI helpers
# ------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Create command-line parser for runtime/config operations."""
    parser = argparse.ArgumentParser(
        description="Telethon offline auto-reply userbot",
    )
    parser.add_argument(
        "--init-files",
        action="store_true",
        help="Create blacklist.json, replies.txt and replied.json if missing.",
    )
    parser.add_argument(
        "--show-blacklist",
        action="store_true",
        help="Print current blacklist user IDs and exit.",
    )
    parser.add_argument(
        "--add-blacklist",
        nargs="+",
        type=int,
        metavar="USER_ID",
        help="Add one or more user IDs to blacklist.json and exit.",
    )
    parser.add_argument(
        "--delete-blacklist",
        nargs="+",
        type=int,
        metavar="USER_ID",
        help="Delete one or more user IDs from blacklist.json and exit.",
    )
    parser.add_argument(
        "--reset-replied",
        action="store_true",
        help="Reset replied.json history and exit.",
    )
    return parser


def handle_cli_actions(args: argparse.Namespace) -> bool:
    """Run requested CLI management operations. Returns True if script should exit."""
    ensure_data_files_exist()

    if args.init_files:
        print("Initialized: blacklist.json, replies.txt, replied.json")
        return True

    if args.show_blacklist:
        blacklist = sorted(load_blacklist(BLACKLIST_PATH))
        print("Blacklist:", blacklist)
        return True

    if args.add_blacklist:
        blacklist = load_blacklist(BLACKLIST_PATH)
        blacklist.update(args.add_blacklist)
        save_json_list(BLACKLIST_PATH, blacklist)
        print("Updated blacklist:", sorted(blacklist))
        return True

    if args.delete_blacklist:
        blacklist = load_blacklist(BLACKLIST_PATH)
        blacklist.difference_update(args.delete_blacklist)
        save_json_list(BLACKLIST_PATH, blacklist)
        print("Updated blacklist:", sorted(blacklist))
        return True

    if args.reset_replied:
        save_replied(REPLIED_PATH, {})
        print("Replied history reset: replied.json")
        return True

    return False


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

def register_activity_handlers(client, events) -> None:
    """Register activity-tracking handlers with broad Telethon compatibility."""
    # Track outgoing messages as activity (indicates user/account is active).
    @client.on(events.NewMessage(outgoing=True))
    async def on_outgoing_message(_event):
        mark_activity("outgoing message")

    # We intentionally avoid MessageRead handlers because some Telethon builds
    # have incompatible MessageRead signatures/behavior across environments.
    # Outgoing messages are the most reliable cross-version activity signal.

async def main() -> None:
    """Entrypoint for running the Telethon userbot."""
    global blacklist_user_ids, replied_user_timestamps, replies_pool

    # Import Telethon only when actually starting the bot,
    # so terminal maintenance commands work without this dependency.
    try:
        from telethon import TelegramClient, events
    except ImportError as exc:
        raise RuntimeError(
            "Telethon is not installed. Run: pip install -r requirements.txt"
        ) from exc

    # Resolve credentials with env-first and constant fallback strategy.
    api_id = API_ID if API_ID else API_ID_FALLBACK
    api_hash = API_HASH if API_HASH else API_HASH_FALLBACK

    if not api_id or not api_hash:
        raise RuntimeError(
            "Missing Telegram credentials. Set API_ID and API_HASH environment variables "
            "or update API_ID_FALLBACK/API_HASH_FALLBACK constants."
        )

    ensure_data_files_exist()

    # Load all data files once at startup.
    blacklist_user_ids = load_blacklist(BLACKLIST_PATH)
    replied_user_timestamps = load_replied(REPLIED_PATH)
    replies_pool = load_replies(REPLIES_PATH)

    client = TelegramClient(SESSION_NAME, api_id, api_hash)

    register_activity_handlers(client, events)

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

        # Limit auto-replies to once per user per REPLY_COOLDOWN_SECONDS.
        last_reply_ts = replied_user_timestamps.get(sender_id, 0)
        if (time.time() - last_reply_ts) < REPLY_COOLDOWN_SECONDS:
            logging.info("Cooldown active for user %s. Skipping.", sender_id)
            return

        # Reply only when account has been inactive for 3+ minutes.
        if not is_offline():
            logging.info("User is active. Not sending auto-reply to %s.", sender_id)
            return

        # Pick random reply line from replies.txt.
        reply_text = random.choice(replies_pool)

        await event.reply(reply_text)
        logging.info("Sent auto-reply to user %s", sender_id)

        # Persist latest reply timestamp for cooldown logic.
        replied_user_timestamps[sender_id] = int(time.time())
        save_replied(REPLIED_PATH, replied_user_timestamps)

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

    parser = build_parser()
    parsed_args = parser.parse_args()

    # Run terminal-only maintenance actions and exit if requested.
    if handle_cli_actions(parsed_args):
        raise SystemExit(0)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Userbot stopped by user.")
    except Exception as exc:
        logging.error("Startup error: %s", exc)
        raise SystemExit(1)
