# yt-dlp Video Downloader Bot

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

A versatile video downloading bot powered by **yt-dlp**. Supports both **Telegram** and **Rocket.Chat** — deploy anywhere, control from your favorite IM. Designed for VPS & NAS linkage.

---

## Features

- **Dual Bot Engine** — Telegram and/or Rocket.Chat, run one or both
- **High Speed** — multi-threaded download with bandwidth limiting
- **Self-Healing** — auto-updates yt-dlp on startup, never stale
- **Live Progress** — real-time download speed, percentage, ETA pushed to chat
- **Concurrency Control** — configurable max concurrent downloads (default 2)
- **Download Archive** — built-in dedup via yt-dlp archive, never re-download the same video
- **Auto Cleanup** — daily at 3:00 AM, removes files older than 24 hours (NAS sync friendly)
- **NAS Ready** — auto-fix permissions (755) + one-command WebDAV service for NAS sync
- **Security** — secrets isolated in `.env`, user ID whitelist for TG
- **Impersonation Support** — bundled curl-cffi for sites requiring browser fingerprinting (e.g. PornHub)

---

## Bot Comparison

| | Telegram | Rocket.Chat |
|---|---|---|
| Listen | User DM | Channel / Group / DM |
| Trigger | Send URL in DM | Send URL in conversation |
| Auth | USER_ID whitelist | Personal Access Token |
| Protocol | HTTP polling (Bot API) | WebSocket (DDP/RealTime) |
| Progress | Edit bot message | Edit bot message |

---

## Quick Start

### Prerequisites

```bash
sudo apt update && sudo apt install -y ffmpeg python3-pip python3-venv
```

### Install (interactive)

```bash
git clone https://github.com/akriamail/yt-dlp-telegram-bot.git
cd yt-dlp-telegram-bot
bash install.sh
```

### Install (one-shot, AI/automation friendly)

```bash
# Telegram only
bash install.sh \
  --tg-token "123456:ABC-DEF123" \
  --tg-user 987654321 \
  --systemd -y

# Rocket.Chat only
bash install.sh \
  --rc-server "https://chat.your-server.com" \
  --rc-user "your-rc-user-id" \
  --rc-token "your-pat-token" \
  --rc-channel "your-channel" \
  --systemd -y

# Both
bash install.sh \
  --tg-token "..." --tg-user 123 \
  --rc-server "..." --rc-user "..." --rc-token "..." \
  --systemd -y
```

---

## Manual Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your bot credentials

# 3. Run
python3 main.py
```

### Telegram Bot Setup

1. Talk to [@BotFather](https://t.me/BotFather), send `/newbot`, save the token
2. Talk to [@userinfobot](https://t.me/userinfobot) to get your User ID
3. Set `TG_TOKEN` and `ALLOWED_USER_ID` in `.env`

### Rocket.Chat Bot Setup

1. In RC, go to your user profile → **Security** → **Personal Access Tokens**
2. Create a token, save the `Token` and your `User ID`
3. Make sure the bot user is in the target conversation (DM / channel / group)
4. Set `RC_USER_ID`, `RC_TOKEN`, `RC_CHANNEL` in `.env`
5. `RC_CHANNEL` accepts: channel name, group name, username (for DM), or raw room ID (24 hex)

---

## Configuration

See [`.env.example`](.env.example) for all options:

| Variable | Default | Description |
|----------|---------|-------------|
| `TG_TOKEN` | — | Telegram Bot Token |
| `ALLOWED_USER_ID` | 0 | Telegram user ID whitelist |
| `RC_SERVER` | https://chat.akria.net | Rocket.Chat server URL |
| `RC_USER_ID` | — | RC user ID |
| `RC_TOKEN` | — | RC Personal Access Token |
| `RC_CHANNEL` | — | RC conversation to monitor (name / username / room ID) |
| `DOWNLOAD_DIR` | ./downloads | Download destination |
| `LIMIT_RATE` | 15M | Bandwidth limit (yt-dlp syntax) |
| `MAX_CONCURRENT` | 2 | Max simultaneous downloads |
| `WEBDAV_USER` | admin | WebDAV auth username |
| `WEBDAV_PASS` | — | WebDAV auth password |
| `WEBDAV_PORT` | 8080 | WebDAV server port |

---

## Auto Cleanup

The bot automatically cleans up downloaded files **every day at 3:00 AM**, removing any files older than 24 hours.

This is designed for the **NAS sync workflow**:
1. Bot downloads video
2. NAS syncs it via WebDAV (within its sync window)
3. Bot deletes it next morning

Hidden files (starting with `.`) are preserved — the download archive (`download-archive` dedup) is never deleted.

No configuration needed. Runs in the background automatically on startup.

---

## Architecture

```
main.py                     ← entry, starts enabled bots + cleanup task
├── downloader.py           ← shared yt-dlp engine with progress callbacks + daily cleanup
├── bot_telegram.py         ← Telegram layer (python-telegram-bot)
├── bot_rocketchat.py       ← Rocket.Chat layer (websockets + httpx)
├── install.sh              ← interactive or parameterized installer
└── setup_webdav.sh         ← WebDAV sync service (rclone)
```

---

## WebDAV Sync (NAS)

```bash
# Read WEBDAV_* from .env and start rclone WebDAV server
chmod +x setup_webdav.sh
./setup_webdav.sh
```

Then add the WebDAV endpoint to your NAS:

```
URL: http://<your-vps-ip>:<WEBDAV_PORT>
User: <WEBDAV_USER>
Pass: <WEBDAV_PASS>
```

| NAS | Connection Type | URL |
|-----|----------------|-----|
| Synology | Cloud Sync / Remote Mount | `http://<ip>:8080` |
| QNAP | HybridMount | `http://<ip>:8080` |
| ZSpace (极空间) | External Device → WebDAV | `http://<ip>:8080` |
| TrueNAS | Cloud Sync | `http://<ip>:8080` |

Workflow: send link → bot downloads → NAS syncs → bot cleans up next morning.

---

## Systemd Service

```bash
# Auto-registered when using --systemd with install.sh
systemctl status yt-dlp-bot
journalctl -u yt-dlp-bot -f
```

---

## Development

```bash
pip install -r requirements.txt
python3 main.py
```

---

## License

MIT
