# 📥 yt-dlp Video Downloader Bot

[简体中文] | [English]

<p align="center">
  <img src="docs/screenshots/bot-preview.png" alt="yt-dlp Bot Demo" width="700">
  <br>
  <em>发送链接 → 自动下载 → 实时进度推送 → WebDAV 同步 NAS → 次日自动清理</em>
</p>

一个基于 `yt-dlp` 的全能视频下载方案，支持 **Telegram** 和 **Rocket.Chat** 双通道，集成 WebDAV 自动同步与每日自动清理，专为 VPS & NAS 联动打造。

A versatile video downloading bot powered by **yt-dlp**. Supports both **Telegram** and **Rocket.Chat** — deploy anywhere, control from your favorite IM. Designed for VPS & NAS linkage.

---

## ✨ 功能特性 / Features

- **双 Bot 引擎 (Dual Bot Engine)** — Telegram + Rocket.Chat 可同时运行
- **极速下载 (High Speed)** — 多线程解析与带宽限速控制
- **自动更新 (Self-Healing)** — 启动时自动更新 yt-dlp 内核
- **实时进度 (Live Progress)** — 进度、速度、剩余时间实时推送
- **下载去重 (Download Archive)** — 内置 yt-dlp archive，重复链接自动跳过
- **每日自动清理 (Auto Cleanup)** — 凌晨 3:00 自动删除 24 小时前的文件，专为 NAS 同步设计
- **NAS 友好 (NAS Ready)** — 自动修正权限 (755) + 一键 WebDAV 同步
- **并发控制 (Concurrency)** — 可配置最大并发下载数
- **安全设计 (Security)** — 敏感信息与代码分离，`.env` 环境隔离
- **指纹模拟 (Impersonation)** — 内置 curl-cffi，支持 PornHub 等需浏览器指纹的站点

---

## Bot 对比 / Bot Comparison

| | Telegram | Rocket.Chat |
|---|---|---|
| 监听 (Listen) | 用户私聊 (User DM) | 频道/群组/私聊 (Channel/Group/DM) |
| 触发 (Trigger) | 私聊发链接 (Send URL in DM) | 对话中发链接 (Send URL in conversation) |
| 鉴权 (Auth) | USER_ID 白名单 (USER_ID whitelist) | Personal Access Token |
| 协议 (Protocol) | HTTP polling (Bot API) | WebSocket (DDP/RealTime) |
| 进度 (Progress) | 编辑 bot 消息 (Edit bot message) | 编辑 bot 消息 (Edit bot message) |

---

## 🚀 快速部署 / Quick Start

### 环境准备 / Prerequisites

```bash
sudo apt update && sudo apt install -y ffmpeg python3-pip python3-venv
```

### 交互式安装 / Interactive

```bash
git clone https://github.com/akriamail/yt-dlp-telegram-bot.git
cd yt-dlp-telegram-bot
bash install.sh
```

### AI 参数化安装 / One-Shot (Automation Friendly)

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

## 📋 手动配置 / Manual Setup

```bash
# 1. 安装依赖 (Install dependencies)
pip install -r requirements.txt

# 2. 配置 (Configure)
cp .env.example .env
# 编辑 .env 填入你的 Bot 凭证

# 3. 运行 (Run)
python3 main.py
```

### Telegram Bot 配置

1. 找 [@BotFather](https://t.me/BotFather) 发 `/newbot` 创建机器人，保存 Token
2. 找 [@userinfobot](https://t.me/userinfobot) 获取你的 User ID
3. 在 `.env` 中设置 `TG_TOKEN` 和 `ALLOWED_USER_ID`

### Rocket.Chat Bot 配置

1. RC 用户设置 → **安全** → **Personal Access Tokens**，创建 Token 并保存
2. 确保 bot 用户在目标对话中（私聊/频道/群组）
3. 在 `.env` 中设置 `RC_USER_ID`、`RC_TOKEN`、`RC_CHANNEL`
4. `RC_CHANNEL` 支持：频道名、群组名、用户名（私聊）、room ID（24位hex）

---

## ⚙️ 配置项 / Configuration

完整配置见 [`.env.example`](.env.example)：

| 变量 (Variable) | 默认值 (Default) | 说明 (Description) |
|-----------------|-------------------|-------------------|
| `TG_TOKEN` | — | Telegram Bot Token |
| `ALLOWED_USER_ID` | 0 | Telegram 用户 ID 白名单 |
| `RC_SERVER` | https://chat.akria.net | Rocket.Chat 服务器地址 |
| `RC_USER_ID` | — | RC 用户 ID |
| `RC_TOKEN` | — | RC Personal Access Token |
| `RC_CHANNEL` | — | RC 监听对话（名称/用户名/room ID） |
| `DOWNLOAD_DIR` | ./downloads | 下载目录 |
| `LIMIT_RATE` | 15M | 限速 (yt-dlp 格式) |
| `MAX_CONCURRENT` | 2 | 最大并发下载数 |
| `WEBDAV_USER` | admin | WebDAV 用户名 |
| `WEBDAV_PASS` | — | WebDAV 密码 |
| `WEBDAV_PORT` | 8080 | WebDAV 端口 |

---

## 🧹 每日自动清理 / Auto Cleanup

Bot **每天凌晨 3:00** 自动删除超过 24 小时的下载文件，专为 NAS 同步工作流设计：

The bot automatically cleans up every day at **3:00 AM**, removing files older than 24 hours.

```
发链接 (Send link) → Bot 下载 (Download) → NAS 同步 (Sync) → 次日凌晨自动清理 (Cleanup)
```

- 隐藏文件（以 `.` 开头）不会被删除，去重记录（archive）永久保留
- 无需任何配置，启动即自动运行

Hidden files (`.` prefix) are preserved — download archive dedup is never deleted. No configuration needed.

---

## 🏗️ 架构 / Architecture

```
main.py                     ← 入口，启动 Bot + 清理任务
├── downloader.py           ← yt-dlp 引擎 + 进度回调 + 每日清理
├── bot_telegram.py         ← Telegram 接入层
├── bot_rocketchat.py       ← Rocket.Chat 接入层 (WebSocket + REST)
├── install.sh              ← 交互式/参数化安装脚本
└── setup_webdav.sh         ← WebDAV 同步服务 (rclone)
```

---

## ☁️ WebDAV 同步 (NAS)

```bash
chmod +x setup_webdav.sh
./setup_webdav.sh
```

在 NAS 上添加 WebDAV 连接：

```
地址 (URL): http://<你的VPS_IP>:<WEBDAV_PORT>
用户 (User): <WEBDAV_USER>
密码 (Pass): <WEBDAV_PASS>
```

| NAS 类型 | 连接方式 (Connection Type) | 地址 (URL) |
|----------|---------------------------|-----------|
| Synology | Cloud Sync / Remote Mount | `http://<ip>:8080` |
| QNAP | HybridMount | `http://<ip>:8080` |
| 极空间 (ZSpace) | 外部设备 → WebDAV | `http://<ip>:8080` |
| TrueNAS | Cloud Sync | `http://<ip>:8080` |

---

## 🔧 Systemd 服务

```bash
# 使用 --systemd 安装时自动注册
systemctl status yt-dlp-bot
journalctl -u yt-dlp-bot -f
```

---

## 💻 开发 / Development

```bash
pip install -r requirements.txt
python3 main.py
```

---

## 📄 许可 / License

MIT
