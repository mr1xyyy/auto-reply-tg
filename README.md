# Telegram Offline Auto-Reply Userbot (Telethon)

Simple Telethon userbot that auto-replies to new private messages only when your account is inactive.

## Features

- Auto-reply only after **3+ minutes** of inactivity.
- Ignore users from `blacklist.json`.
- Pick random reply from `replies.txt`.
- Auto-reply to the same user no more than once per hour (`replied.json`).
- Blacklist management from terminal.

## Files

- `auto_reply_userbot.py` — main script.
- `blacklist.json` — list of blocked user IDs.
- `replies.txt` — one reply per line.
- `replied.json` — last auto-reply timestamps per user.

## Requirements

- Python 3.9+
- Dependencies from `requirements.txt`

Quick install:

```bash
pip install -r requirements.txt
```

## Configure API credentials

Get `API_ID` and `API_HASH` at [my.telegram.org](https://my.telegram.org).

### Windows CMD

```cmd
set API_ID=123456
set API_HASH=your_api_hash
python auto_reply_userbot.py
```

### Windows PowerShell

```powershell
$env:API_ID="123456"
$env:API_HASH="your_api_hash"
python .\auto_reply_userbot.py
```

### Linux/macOS

```bash
export API_ID=123456
export API_HASH="your_api_hash"
python auto_reply_userbot.py
```

## Blacklist commands

```bash
python auto_reply_userbot.py --init-files
python auto_reply_userbot.py --show-blacklist
python auto_reply_userbot.py --add-blacklist 123456789 987654321
python auto_reply_userbot.py --delete-blacklist 123456789
python auto_reply_userbot.py --reset-replied
```

## Run

```bash
python auto_reply_userbot.py
```

## Notes

- Works for private chats only.
- If `replies.txt` is missing, script creates it with a default line.
- If you still see `outbox=True` in errors, update your local `auto_reply_userbot.py` file.


`replied.json` format: `{ "<user_id>": <last_reply_unix_ts> }`.
