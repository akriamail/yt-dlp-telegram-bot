# yt-dlp-telegram-bot agent notes

Keep this file in sync with its peer agent instruction file.

## What this is

- **A video downloader bot.** Send a link over Telegram or Rocket.Chat → yt-dlp downloads it → live
  progress is pushed back → the file lands in `downloads/`, where a NAS pulls it over WebDAV → files
  older than 24h are deleted the following day.
- **Two front ends, one engine.** `bot_telegram.py` (python-telegram-bot) and `bot_rocketchat.py`
  (WebSocket DDP + REST). `downloader.py` is the only copy of the yt-dlp engine — **never write a
  second one**; the two would drift and then nobody could say which behaviour was real.
- **Standalone on a VPS, not in any cluster.** VPS `vmiss` `38.47.106.216`, code at `/opt/yt-dlp-bot`,
  venv + systemd unit `yt-dlp-bot.service`. There is **no Dockerfile, no CI workflow, no image and no
  manifest** — this is the one service in `services/` that is not deployed by tag.

## Deploy is manual — a merged feature is not a live feature

The VPS runs from a **git checkout**; nothing pulls for you.

```bash
ssh vmiss 'cd /opt/yt-dlp-bot && git pull --ff-only && systemctl restart yt-dlp-bot'
```

**This has bitten us.** Daily cleanup was merged in `2411cc8` (2026-07-11) and the VPS sat on
`cebae3a` for two months, so the feature never ran and `downloads/` grew to 2.5 GB unnoticed. Before
debugging "the feature does not work", **read `git log --oneline -1` on the VPS first** — the answer
is often that the code is simply not there.

## Daily cleanup is in-process, not a timer

`downloader.py:daily_cleanup()` is registered as an asyncio task in `main.py` (both the shared-loop
and the TG-only paths). **There is no cron job and no systemd timer, and their absence is not a
fault** — hunting for one is a dead end.

It sleeps until **03:00 UTC** (= 11:00 Beijing; the README's "3:00 AM" means UTC, not local), then
deletes files older than 24h in `download_dir`. Dotfiles are skipped on purpose, and that is the only
reason `.archive.txt` survives.

`.archive.txt` is yt-dlp's download archive (dedup). Deleting the videos does **not** clear it, so a
deleted link re-sent to the bot downloads nothing. If a file must be re-fetchable, strip its line
from the archive first.

## WebDAV: the real port is 8081

```text
rclone serve webdav /opt/yt-dlp-bot/downloads --addr :8081 --user admin --pass <from .env>
unit rclone-webdav.service      client URL http://38.47.106.216:8081
```

**Never 8080.** That belongs to nginx on the same host (`listen 8080 ssl; server_name
hk2.changuoo.com` — the subscription service). 8081 exists only because the unit was edited by hand
after that collision, so treat 8081 as the interface other machines are already configured against.

`setup_webdav.sh` used to hard-code `PORT=8080`, ignoring `.env` entirely; re-running it would have
put rclone back on nginx's port and taken WebDAV down. It now reads `PORT=${WEBDAV_PORT:-8081}`.
**Keep it that way, and write 8081 into any doc you touch** — the docs drifted to 8080 for months.

The password is passed as a command-line argument in `ExecStart`, so anyone who can read the unit can
read it. Accepted for a personal VPS; the upgrade path is rclone's encrypted config file.

## Config and secrets

Everything comes from `.env`, which is **gitignored — never commit it, and never paste its values
into the docs**. The Rocket.Chat credentials in `README.md` / `DEVELOPMENT.md` are placeholders and
must stay placeholders.

| var | meaning |
|---|---|
| `TG_TOKEN` / `ALLOWED_USER_ID` | Telegram bot; only that user id is served |
| `RC_SERVER` / `RC_USER_ID` / `RC_TOKEN` / `RC_CHANNEL` | Rocket.Chat, authenticated by a **Personal Access Token**, not a password. `RC_CHANNEL` accepts a name, username or room id, DMs included |
| `DOWNLOAD_DIR` / `LIMIT_RATE` / `MAX_CONCURRENT` | default `./downloads`, `15M`, `2` |
| `WEBDAV_USER` / `WEBDAV_PASS` / `WEBDAV_PORT` | read by `setup_webdav.sh`; default port 8081 |

`main.py` starts TG, RC or both depending on what is configured. With RC in play both bots share one
asyncio loop (`amain`) — which is also the path that registers the cleanup task. A config change here
is a restart, not a redeploy.

## Runtime behaviour worth knowing

- **yt-dlp self-updates on every start** (`downloader.update_yt_dlp()`), so a restart can change
  download behaviour with no repo change. It is also why site breakage usually clears with a restart.
- `requirements.txt` pins `yt-dlp[default]`: the extra brings in `curl_cffi` for TLS-fingerprint
  impersonation, which some sites require.
- Downloads are deduped through `--download-archive`. Concurrent downloads are capped by
  `MAX_CONCURRENT` and rate-limited by `LIMIT_RATE`.

## Things not to redo

- **X/Twitter cookie automation** (`twikit`, login-and-scrape) was tried and **reverted** (`cebae3a`)
  — it never worked and the dependency was heavy. The agreed path is a user-exported `cookies.txt`
  passed via `--cookies`. Do not reintroduce it.
- `setup_webdav.sh` and `install.sh` are the only install paths; both are meant to be re-runnable.

## Hard rules

- **Never commit `.env` or any real credential.** Sanitise every example.
- **Never move WebDAV to 8080**, and never let `setup_webdav.sh` drift back to it.
- **Do not replace the in-process cleanup with cron or a systemd timer** without journaling why; the
  current shape is deliberate and its absence of a timer has already been mis-diagnosed once.
- `downloads/` holds the user's own media. Deleting from it is a **Class A** operation under the
  parent repo's rules: list exactly what will go, get approval, then delete.
