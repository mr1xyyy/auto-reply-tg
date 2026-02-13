# Telegram Offline Auto-Reply Userbot (Telethon)

This project provides a Python **userbot** script that automatically replies to **new private messages** only when your account appears inactive.

## Features

- Replies only when there was no recent activity for **3+ minutes**.
- Skips users listed in `blacklist.json`.
- Uses dynamic random replies from `replies.txt`.
- Sends only **one** auto-reply per user, tracked in `replied.json`.
- Async implementation with **Telethon**.
- Works from terminal on **CMD / PowerShell / Linux shell**.
- Supports blacklist management directly from terminal commands.

## File Structure

- `auto_reply_userbot.py` — main script.
- `blacklist.json` — JSON array of user IDs that should never get auto-replies.
- `replies.txt` — text file with one reply per line.
- `replied.json` — JSON array of user IDs that already received auto-reply.

## Requirements

- Python 3.9+
- Telethon

Install dependency:

```bash
pip install telethon
```

## Telegram API credentials

You need Telegram API credentials from [my.telegram.org](https://my.telegram.org):

- `API_ID`
- `API_HASH`

Set environment variables (recommended).

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

### Linux/macOS bash

```bash
export API_ID=123456
export API_HASH="your_api_hash"
python auto_reply_userbot.py
```

> You can also put credentials into fallback constants inside `auto_reply_userbot.py`, but environment variables are safer.

## Manage blacklist from terminal

You asked to work with `blacklist.json` from terminal — use these commands:

```bash
python auto_reply_userbot.py --init-files
python auto_reply_userbot.py --show-blacklist
python auto_reply_userbot.py --add-blacklist 123456789 987654321
python auto_reply_userbot.py --delete-blacklist 123456789
```

What they do:
- `--init-files` creates missing files (`blacklist.json`, `replies.txt`, `replied.json`).
- `--show-blacklist` prints the current blacklist.
- `--add-blacklist` adds one or more user IDs to `blacklist.json`.
- `--delete-blacklist` removes one or more user IDs from `blacklist.json`.

## Data file examples

### `blacklist.json`

```json
[123456789, 987654321]
```

### `replies.txt`

```text
I'm away right now. I'll reply soon.
Thanks for your message! I'll get back to you later.
Currently offline. Will answer when I'm back.
```

### `replied.json`

```json
[]
```

## Run userbot

```bash
python auto_reply_userbot.py
```

On first run, Telethon will ask for login/verification in terminal and create a local session file.

## Notes

- Offline behavior is based on script-side activity tracking and `OFFLINE_THRESHOLD_SECONDS = 180`.
- Auto-reply is sent only for private chats.
- If `replies.txt` is missing, script creates it with a default reply.


## Troubleshooting (CMD/PowerShell)

If you see an error like:

`TypeError: MessageRead.__init__() got an unexpected keyword argument 'outbox'`

do the following:

1. Make sure you are running the **latest script** from this repository.
2. Upgrade Telethon:

```bash
pip install -U telethon
```

3. Start again:

```bash
python auto_reply_userbot.py
```

The current script avoids MessageRead activity hooks entirely for maximum Telethon compatibility.


If your traceback still shows `outbox=True`, you are running an older local copy — replace it with the latest `auto_reply_userbot.py` from this repository.
