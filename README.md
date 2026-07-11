# yt-dlp Video Downloader Bot

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

A versatile video downloading bot powered by **yt-dlp**. Supports both **Telegram** and **Rocket.Chat** — deploy anywhere, control from your favorite IM. Designed for VPS & NAS linkage.

---

## Features

- **Dual Bot Engine** — Telegram and/or Rocket.Chat, run one or both
- **High Speed** — multi-threaded download with bandwidth limiting
- **Self-Healing** — auto-updates yt-dlp on startup, never stale
- **Live Progress** — real-time download speed, percentage, ETA
- **NAS Ready** — auto-fix permissions (755) + one-command WebDAV sync
- **Security** — secrets isolated in `.env`, user ID whitelist for TG
- **Concurrency Control** — configurable max concurrent downloads

---

## Bot Comparison

| | Telegram | Rocket.Chat |
|---|---|---|
| Listen | User DM | Channel / Group |
| Trigger | Send URL in DM | Send URL in channel |
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
2. Create a token, save the `Token` (not just last N chars) and your `User ID`
3. Make sure the bot user is invited to the target channel/group
4. Set `RC_USER_ID`, `RC_TOKEN`, `RC_CHANNEL` in `.env`

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
| `RC_CHANNEL` | 渠道监控 | RC channel/group to monitor |
| `DOWNLOAD_DIR` | ./downloads | Download destination |
| `LIMIT_RATE` | 15M | Bandwidth limit (yt-dlp syntax) |
| `MAX_CONCURRENT` | 2 | Max simultaneous downloads |

---

## Architecture

```
main.py                     ← entry, starts enabled bots
├── downloader.py           ← shared yt-dlp engine with progress callbacks
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

Then add the WebDAV endpoint to your NAS (Synology / QNAP / ZSpace):

```
URL: http://<your-vps-ip>:8080
User: <WEBDAV_USER>
Pass: <WEBDAV_PASS>
```

---

## Systemd Service

```bash
# Auto-registered when using --systemd with install.sh
systemctl status yt-dlp-bot
journalctl -u yt-dlp-bot -f
```

---

## Development

```
pip install -r requirements.txt
python3 main.py
```

---

## License

MIT
