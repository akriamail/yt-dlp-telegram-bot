# Development & Maintenance Guide

A comprehensive guide for developers and maintainers of the yt-dlp Video Downloader Bot.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Code Structure](#2-code-structure)
3. [Unified Entry Point](#3-unified-entry-point)
4. [Download Engine](#4-download-engine)
5. [Telegram Bot Layer](#5-telegram-bot-layer)
6. [Rocket.Chat Bot Layer](#6-rocketchat-bot-layer)
7. [DDP WebSocket Protocol](#7-ddp-websocket-protocol)
8. [Concurrency Model](#8-concurrency-model)
9. [Install Script](#9-install-script)
10. [Environment Configuration](#10-environment-configuration)
11. [Systemd Service](#11-systemd-service)
12. [WebDAV Sync](#12-webdav-sync)
13. [Troubleshooting](#13-troubleshooting)
14. [Changelog](#14-changelog)

---

## 1. Architecture Overview

```
User ── Telegram ──┐                    ┌── yt-dlp ──▶ Download
                   ├── main.py ────────▶┤
User ── RC Chat ──┘ (detect config)    └── callback ─▶ Progress to IM
```

The bot is a **layered Python application** that separates concerns cleanly:

- **Engine layer** (`downloader.py`): The yt-dlp wrapper. Knows nothing about Telegram or Rocket.Chat. Emits pure callbacks.
- **Adapter layers** (`bot_telegram.py`, `bot_rocketchat.py`): Convert IM-specific events (message received) into download calls, and download progress back into IM messages.
- **Entry point** (`main.py`): Reads `.env`, instantiates the right adapters, starts the event loops.

This design means adding a third IM (e.g. Discord, Slack, WhatsApp) is just writing a new `bot_xxx.py` and registering it in `main.py`.

### Data Flow

```
1. User sends URL in IM
2. Bot adapter receives message
3. downloader.run_download() is called with callbacks
4. yt-dlp process spawns
5. Progress parsed from stdout → on_progress() callback
6. Bot adapter calls edit_message_text / chat.update
7. On finish: on_done() or on_error() callback
```

---

## 2. Code Structure

```
yt-dlp-telegram-bot/
├── main.py              # Unified entry point (class A start)
├── downloader.py        # Shared yt-dlp engine
├── bot_telegram.py      # Telegram adapter
├── bot_rocketchat.py    # Rocket.Chat adapter
├── install.sh           # Interactive & parameterized installer
├── setup_webdav.sh      # rclone WebDAV service
├── .env.example         # Configuration template (full reference)
├── requirements.txt     # Python dependencies
├── README.md            # User-facing documentation
├── DEVELOPMEN.md        # This file
└── AGENTS.md            # AI assistant context (auto-synced)
```

### File Responsibilities

| File | Lines | Dependencies | Purpose |
|------|-------|--------------|---------|
| `main.py` | ~100 | downloader, bot_*, dotenv | Config load, bot detection, lifecycle |
| `downloader.py` | ~125 | stdlib only | yt-dlp update, URL cleaning, async subprocess |
| `bot_telegram.py` | ~80 | python-telegram-bot, downloader | TG message handler, progress editing |
| `bot_rocketchat.py` | ~180 | websockets, httpx, downloader | DDP WS connect, room subscribe, REST messages |
| `install.sh` | ~200 | bash, apt, systemd | Install, configure, register service |
| `setup_webdav.sh` | ~45 | bash, rclone | WebDAV sync endpoint |

---

## 3. Unified Entry Point

`main.py` is the starting point. Flow:

```python
def main():
    # 1. Update yt-dlp (sync, first thing)
    dl.update_yt_dlp()

    # 2. Read .env
    load_dotenv()

    # 3. Detect which bots are configured
    enable_tg = bool(tg_token and tg_user)
    enable_rc = bool(rc_uid and rc_token)

    # 4. Dispatch
    if enable_tg and not enable_rc:
        # Pure TG: delegates to python-telegram-bot's own polling loop
        TelegramBot(...).run()
    else:
        # RC involved (or both): runs asyncio event loop
        # TG runs in daemon thread, RC in asyncio
        loop = asyncio.new_event_loop()
        if enable_tg: threading.Thread(target=TG.run, daemon=True).start()
        if enable_rc: loop.run_until_complete(rc_bot.run_forever())
```

### Why this split?

`python-telegram-bot`'s `Application.run_polling()` manages its own asyncio event loop internally. When RC is also running, we need a single shared loop. The split makes both scenarios clean:

- **TG-only**: Simple, delegate entirely to `python-telegram-bot`
- **RC-only or Both**: We own the loop; TG runs in a thread via `Thread(target=tg.run, daemon=True)`

### Shutdown Sequence

```python
# Signal handler registered on loop:
loop.add_signal_handler(signal.SIGINT, loop.stop)
loop.add_signal_handler(signal.SIGTERM, loop.stop)

# On shutdown:
# 1. RC task gets CancelledError (which it re-raises from run_forever)
# 2. we call rc_bot.shutdown() → closes httpx client
# 3. loop closes
# If TG thread is running, it's a daemon thread — exits when process exits
```

---

## 4. Download Engine

`downloader.py` — the only file that knows about yt-dlp.

### update_yt_dlp()

Always called on startup before doing anything else:

```python
subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"])
```

This ensures `yt-dlp` is always the latest version. If yt-dlp's upstream site parsers change, the next restart will pick up the fix automatically.

### clean_url()

URL sanitization before passing to yt-dlp. Two transformations:

1. **Mobile-to-desktop domain rewrite**: `m.pornhub.com` → `cn.pornhub.com` (PH site redirects mobile to cn domain)
2. **viewkey preserve**: Some PH URLs have `viewkey` in query params that get lost when stripping query strings; we extract and reconstruct the canonical URL

### build_cmd()

Constructs the shell command. Key flags:

| Flag | Value | Purpose |
|------|-------|---------|
| `--user-agent` | Chrome 120 UA | Bypass bot detection |
| `--no-playlist` | — | Only download single video, not entire playlist |
| `--socket-timeout` | 60 | Network read timeout |
| `--retries` | 10 | Retry on failure |
| `--limit-rate` | from config | Bandwidth limiting |
| `-f` | tiered format | `bestvideo[ext=mp4]+bestaudio[ext=m4a]` → `best[ext=mp4]` → `best` |
| `-P` | download_dir | Output directory |
| `--newline` | — | stdout progress on separate lines (parsing requirement) |
| `--no-mtime` | — | Don't set file modification time (simplifies NAS sync) |
| `--exec chmod 755` | — | Fix permissions for NAS compatibility |

### run_download()

The async download function. Signature:

```python
async def run_download(
    url: str,
    download_dir: str,
    limit_rate: str,
    on_progress=None,     # callable(percent, speed, eta)
    on_done=None,         # async callable()
    on_error=None,        # async callable(stderr_str)
)
```

**Stdout pipeline:**

yt-dlp with `--newline` outputs lines like:

```
[download]  45.2% of ~83.69MiB at  8.32MiB/s ETA 00:05
```

We parse these with regex:

```
\[download\]\s+([\d.]+)%.*?at\s+([\d.]+\w+/s)\s+ETA\s+([\d:]+)
```

**Stderr capture:**

Stderr is read concurrently in a background task, captured for error reporting. Only the last 500 bytes are retained.

**Throttling:**

Progress callbacks fire at most once per 10 seconds, to avoid rate-limiting the IM API.

**Callbacks:**

- `on_progress(pct, speed, eta)` — **synchronous** (written for synchronous use). Called from the stdout parsing loop. The TG adapter wraps its async `edit_message_text` in `asyncio.ensure_future()`.
- `on_done()` and `on_error(stderr)` — **async**. Called after process exit.

---

## 5. Telegram Bot Layer

### Class: TelegramBot

```python
class TelegramBot:
    def run(self):
        app = ApplicationBuilder().token(self.token).build()
        app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        )
        app.run_polling()
```

- **Auth**: `ALLOWED_USER_ID` whitelist — only the configured user's messages are processed
- **Trigger**: Any non-command text message starting with `http`
- **Progress**: Uses `context.bot.edit_message_text()` on the status message. `asyncio.ensure_future` is used in the sync `on_progress` callback to schedule the async API call on the event loop.

### Constraints

- **Single user**: No multi-user support. This is by design — keeping it simple for personal VPS use.
- **Polling-based**: No webhooks. python-telegram-bot's polling is sufficient.
- **Max one command per 10 seconds**: Rate-limited by the progress callback throttle.

---

## 6. Rocket.Chat Bot Layer

### Class: RocketChatBot

```python
class RocketChatBot:
    async def run_forever(self):
        # 1. Resolve channel name → room_id via REST API
        # 2. Connect to DDP WebSocket
        # 3. Login via REST, resume on WS
        # 4. Subscribe to stream-room-messages
        # 5. Loop: receive messages → extract URLs → download
```

### Dual-API Strategy

RC doesn't have a single channel for both sending and receiving. We use **two APIs**:

| Operation | API | Why |
|-----------|-----|-----|
| Receive messages | **WebSocket** DDP subscribe | RealTime API — only way to get push notifications |
| Send messages | **REST** `/api/v1/chat.sendMessage` | Simpler, no need for WS method calls |
| Update messages | **REST** `/api/v1/chat.update` | REST fully supports this |

### Auth Flow (tricky part)

The DDP WebSocket protocol expects a `login` method call. Direct PAT (Personal Access Token) login over WS sometimes fails cryptographically. The reliable flow:

```
1. REST POST /api/v1/login { "resume": "<PAT>" }
      → returns data.authToken (a short-lived session token)
2. WS method call: login { "resume": "<authToken>" }
      → returns success
3. Now subscribed and receiving messages
```

### Message Reception

All RC messages come through the `stream-room-messages` subscription. The payload structure:

```json
{
  "msg": "changed",
  "fields": {
    "args": [
      {
        "msg": "https://www.youtube.com/watch?v=xxxx",
        "u": { "username": "user123" },
        "tmid": null        // null = top-level, non-null = thread reply
      }
    ]
  }
}
```

**Filters in message loop:**

| Filter | Reason |
|--------|--------|
| `sender == "clara"` | Skip own messages (infinite loop prevention) |
| `"tmid" in m` | Skip thread replies (they're often replies to Clara's progress messages) |
| Not starting with `http` | Not a downloadable URL |

### Room Resolution

```python
async def _resolve_room(self, name: str) -> str:
    # Try channels (public) first, then groups (private)
    for endpoint in ("channels.info", "groups.info"):
        r = await self._http.get(f"/api/v1/{endpoint}", params={"roomName": name})
        ...
```

Public channels: `channels.info` endpoint
Private groups: `groups.info` endpoint

---

## 7. DDP WebSocket Protocol

Rocket.Chat uses a modified version of the [DDP (Distributed Data Protocol)](https://github.com/meteor/meteor/blob/devel/packages/ddp/DDP.md) over WebSocket.

### Connection Sequence

```
CLIENT → {"msg": "connect", "version": "1", "support": ["1", "pre2", "pre1"]}
SERVER ← {"msg": "connected", "session": "sJ3k2L1mN5"}

CLIENT → {"msg": "method", "method": "login", "params": [{"resume": "<token>"}], "id": "1"}
SERVER ← {"msg": "result", "id": "1", "result": {"id": "...", "token": "..."}}

CLIENT → {"msg": "sub", "id": "sub1", "name": "stream-room-messages",
           "params": ["<room_id>", {"useCollection": false, "args": []}]}
SERVER ← {"msg": "ready", "subs": ["sub1"]}
```

### Message Loop

After subscribe, the server pushes messages:

```
SERVER → {"msg": "changed", "collection": "stream-room-messages",
           "fields": {"args": [[message_object]]}}
```

### Keepalive

```python
websockets.connect(ws_url, ping_interval=25, ping_timeout=10, ...)
```

Additionally, we handle RC's own **Meteor-level ping/pong**:

```python
if data.get("msg") == "ping":
    pong = {"msg": "pong"}
    if "id" in data: pong["id"] = data["id"]
    await ws.send(json.dumps(pong))
```

### Reconnection

On `ConnectionClosed` (server restart, network blip, idle timeout): wait 5 seconds, retry indefinitely. On other exceptions: wait 15 seconds, retry. This runs forever — `asyncio.CancelledError` is the only exit.

---

## 8. Concurrency Model

### Scenarios

| Scenario | Loop | TG | RC |
|----------|------|----|----|
| TG-only | python-telegram-bot internal | `run()` direct | — |
| RC-only | Shared asyncio loop | — | `run_forever()` as task |
| TG + RC | Shared asyncio loop | `start_polling()` as task | `run_forever()` as task |

### Concurrency Architecture

All bots run as **asyncio tasks** in a single event loop:

```
main.py: loop.run_until_complete(amain())
└── asyncio.wait(tasks, return_when=FIRST_EXCEPTION)
    ├── TelegramBot.start_polling()   ← async task
    └── RocketChatBot.run_forever()   ← async task
```

- **TG + RC**: both are `asyncio.Task`s in the same loop. python-telegram-bot's `start_polling()` is an async method added specifically for this shared-loop mode.
- **TG-only**: fast path via `TelegramBot.run()` which delegates to `app.run_polling()` (its own loop management).
- **RC-only**: single `run_forever()` task in the shared loop.

### Download Semaphore

```python
# RocketChatBot
self.sem = asyncio.Semaphore(max_concurrent)

async def _download(self, url, room_id):
    async with self.sem:
        ...
```

Limits concurrent yt-dlp processes. Default: 2. This prevents:
- Bandwidth saturation
- Disk I/O contention
- yt-dlp process memory blowup

### Thread Safety

- `downloader.py` is fully async, no thread involvement
- All bots run as asyncio tasks in the same loop — no thread safety concerns
- The `on_progress` callback from downloader is synchronous; RC adapter wraps API calls in `asyncio.ensure_future()` to schedule on the shared loop
- No shared mutable state between bot instances

---

## 9. Install Script

`install.sh` supports two modes:

### Interactive Mode

```bash
bash install.sh
```

Asks questions one by one: bot type, tokens, paths, systemd.

### AI/Parameterized Mode

```bash
bash install.sh \
  --tg-token "..." --tg-user 123 \
  --rc-server "https://chat.akria.net" \
  --rc-user "v6mAePSF5WgT4ed7D" \
  --rc-token "eJD75g7c..." \
  --rc-channel "渠道监控" \
  --download-dir "/data/downloads" \
  --limit-rate "20M" \
  --max-concurrent "3" \
  --install-dir "/opt/yt-dlp-bot" \
  --systemd -y
```

### What it Does

| Step | Action |
|------|--------|
| 1. System deps | `apt install ffmpeg python3-pip python3-venv` |
| 2. Config | Generates `.env` from parameters |
| 3. Code | Copies `.py` files to install dir |
| 4. Venv | Creates `.venv`, `pip install -r requirements.txt` |
| 5. systemd | Optionally writes and enables service unit |
| 6. Done | Prints paths and manual start instructions |

### Uninstall

```bash
bash install.sh --uninstall
```

Stops and removes systemd service, optionally removes install directory.

---

## 10. Environment Configuration

Full reference — see `.env.example` for defaults.

### Shared

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DOWNLOAD_DIR` | string | `./downloads` | Output directory |
| `LIMIT_RATE` | string | `15M` | yt-dlp syntax: `15M`, `10K`, `1G`, or `0` (unlimited) |
| `MAX_CONCURRENT` | int | `2` | Max parallel downloads |

### Telegram

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TG_TOKEN` | string | — | Bot token from @BotFather |
| `ALLOWED_USER_ID` | int | `0` | TG user ID whitelist |

### Rocket.Chat

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RC_SERVER` | string | `https://chat.akria.net` | RC server base URL |
| `RC_USER_ID` | string | — | RC user ID (from profile) |
| `RC_TOKEN` | string | — | RC Personal Access Token |
| `RC_CHANNEL` | string | `渠道监控` | Channel/group name to listen |
| `RC_RECONNECT_DELAY` | int | `5` | WS reconnect delay (seconds) |

### WebDAV

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WEBDAV_USER` | string | `admin` | WebDAV auth username |
| `WEBDAV_PASS` | string | — | WebDAV auth password |
| `WEBDAV_PORT` | int | `8080` | WebDAV server port |

---

## 11. Systemd Service

### Unit File

```ini
[Unit]
Description=yt-dlp Video Downloader Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/yt-dlp-bot
Environment=PATH=/opt/yt-dlp-bot/.venv/bin:/usr/local/bin:/usr/bin
ExecStart=/opt/yt-dlp-bot/.venv/bin/python3 /opt/yt-dlp-bot/main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Common Commands

```bash
# Status
systemctl status yt-dlp-bot

# Logs (live)
journalctl -u yt-dlp-bot -f

# Restart after config change
systemctl restart yt-dlp-bot

# Stop
systemctl stop yt-dlp-bot
```

### After Changing .env

The service reads `.env` from `WorkingDirectory` at startup. After editing `.env`:

```bash
systemctl restart yt-dlp-bot
```

No other steps needed — the service does not cache the config.

---

## 12. WebDAV Sync

`setup_webdav.sh` installs rclone and configures it as a systemd service:

```ini
ExecStart=/usr/bin/rclone serve webdav $SYNC_DIR --addr :$PORT --user $USER --pass $PASS
```

Security concern: the password is passed as a command-line argument to `ExecStart`. Any user with `systemctl` access can read it. For a personal VPS where you trust the root user, this is acceptable. For production, use rclone's `--config` with an encrypted config file.

### NAS Integration

| NAS | Connection Type | URL |
|-----|----------------|-----|
| Synology | Cloud Sync / Remote Mount | `http://<vps-ip>:8080` |
| QNAP | HybridMount | `http://<vps-ip>:8080` |
| ZSpace (极空间) | External Device → WebDAV | `http://<vps-ip>:8080` |
| TrueNAS | Cloud Sync | `http://<vps-ip>:8080` |

---

## 13. Troubleshooting

### Bot Won't Start

```
❌ 未检测到任何 Bot 配置！
```

→ No bot credentials found in `.env`. Check that either TG or RC credentials are set.

### yt-dlp Update Fails

```log
❌ yt-dlp 更新失败: ...
```

→ Usually a network issue or pip environment problem. On a fresh VPS, try:

```bash
pip3 install yt-dlp
```

### RC Login Fails

```log
Login failed: ...
```

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `403` | PAT expired or wrong | Delete and regenerate PAT in RC Settings → Security |
| `401` | User ID doesn't match PAT | Check `RC_USER_ID` matches the user that created the PAT |
| `[noMethod] login` | WS protocol mismatch | RC version may use different DDP. Check RC version (`chat.akria.net/api/info`) |
| Timeout | Network issue | Check connectivity from VPS to RC server |

### RC No Messages Received

- Confirm Clara is invited to the channel/group
- Check the channel name in `.env` matches exactly (case-sensitive for private groups)
- Check logs for `✅ Subscribed 渠道监控` — if this line appears, WS is connected

### WebDAV Connection Refused

```bash
# Server not running
systemctl status rclone-webdav.service

# Check firewall (if using ufw)
ufw status
# → Ensure port 8080 is open
```

### Download Fails

```log
❌ 下载失败: ...
```

→ yt-dlp stderr is appended to the error message, e.g.:

```
ERROR: [YouTube] xxxxx: Sign in to confirm you're not a bot
```

Solutions:
- Update yt-dlp (restart the bot)
- Add cookies (see yt-dlp docs: `--cookies-from-browser`)
- Increase `--retries` (modify `build_cmd()`)

---

## 14. Changelog

### v2.0.0 (unreleased)

**Major rewrite** — dual IM support, modular architecture.

**Breaking changes:**
- `.env` format changed — added `RC_SERVER`, `RC_USER_ID`, `RC_TOKEN`, `RC_CHANNEL`, `MAX_CONCURRENT`; `TG_TOKEN` and `ALLOWED_USER_ID` retained but optional
- `main.py` no longer starts without any bot config — must set TG or RC credentials
- `install.sh` replaces manual setup as the recommended path

**New files:**
- `bot_rocketchat.py` — Rocket.Chat bot via WebSocket DDP protocol
- `bot_telegram.py` — Extracted Telegram adapter from monolithic `main.py`
- `downloader.py` — Shared yt-dlp engine with callback architecture
- `install.sh` — Interactive and parameterized installer
- `DEVELOPMENT.md` — This document
- `AGENTS.md` — AI assistant context

**Changed files:**
- `main.py` — Rewritten as unified entry point; TG+RC 共享同一事件循环
- `bot_telegram.py` — 新增 `start_polling()` async 方法，支持共享事件循环
- `bot_rocketchat.py` — 新增 `_http_to_ws()` 协议转换，send_msg/update_msg 增加失败日志
- `requirements.txt` — Added `websockets`, `httpx`; reordered
- `README.md` — Dual-IM documentation
- `.env.example` — Complete rewrite with all options

**Removed:**
- Old monolithic `main.py` with TG-only logic

**Fixes from code review:**
- 修复：TG+RC 双启动冲突 — 不再将 TG 放入后台线程，改用 `start_polling()` 在共享事件循环运行
- 修复：`MAX_CONCURRENT` 未传递 — main.py 读取环境变量并传入 RocketChatBot 构造函数
- 修复：WS URL 仅支持 `https://` — 新增 `_http_to_ws()` 正则处理 `http://` → `ws://`
- 修复：RC 消息发送/更新失败被吞没 — send_msg/update_msg 检查 HTTP 状态并记录警告日志

### v1.0.0

Initial release. Telegram-only, single-file monolithic bot.

---
