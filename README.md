# 📥 Universal Video Downloader Bot (yt-dlp-telegram-bot)

[Simplified Chinese] | [English]

一个基于 `yt-dlp` 的全能视频下载方案，集成 Telegram 机器人控制与 WebDAV 自动同步，专为海外 VPS 与私有云 (NAS) 联动打造。
A versatile video downloading solution based on `yt-dlp`. Features Telegram Bot control and auto WebDAV synchronization, designed for VPS & NAS linkage.

---

## ✨ 核心功能 / Key Features

- **🚀 极速下载 (High-Speed)**: 支持多线程解析与带宽限速控制。
- **🔄 自动更新 (Self-Healing)**: 启动时自动检查更新 `yt-dlp` 内核，确保解析永不失效。
- **📊 状态反馈 (Live Progress)**: TG 实时推送进度、速度与剩余时间 (ETA)。
- **☁️ NAS 友好 (NAS Ready)**: 自动修正权限 (755) 并提供一键 WebDAV 同步服务。
- **🛡️ 安全设计 (Security)**: 敏感信息与代码彻底分离，支持 `.env` 环境隔离。

---

## 🛠️ 快速部署 / Quick Start

### 🤖 申请 Telegram 机器人 / Create Your Bot

如果您还没有机器人，请按照以下步骤申请：

1. **获取 Token**:
   - 在 Telegram 中搜索 [@BotFather](https://t.me/BotFather) 并点击 `Start`。
   - 发送 `/newbot`，按照提示为你的机器人起个名字（例如：`MyDownloader`）。
   - 为其设置一个以 `_bot` 结尾的用户名（例如：`akria_dl_bot`）。
   - **保存** 随后生成的 `HTTP API Token`（即 `TG_TOKEN`）。

2. **获取您的 User ID**:
   - 搜索 [@userinfobot](https://t.me/userinfobot) 并发送任意消息。
   - 它会返回一串数字（例如：`123456789`），这就是你的 `ALLOWED_USER_ID`。
   - *注意：设置此 ID 是为了防止陌生人恶意盗用你的 VPS 流量。*

3. **激活机器人**:
   - 点击进入你刚创建的机器人对话框，点击 `Start`，否则它无法主动向你发送消息。
### 1. 环境准备 / Environment
```bash
# 克隆项目 (Clone)
git clone [https://github.com/akriamail/yt-dlp-telegram-bot.git](https://github.com/akriamail/yt-dlp-telegram-bot.git)
cd yt-dlp-telegram-bot

# 安装依赖 (Install)
sudo apt update && sudo apt install -y ffmpeg rclone
pip install -r requirements.txt
```
### 2. 配置环境 / Configuration
创建 .env 文件并填入信息 (Create .env and fill in secrets):
```bash
# Telegram Bot 配置
TG_TOKEN=你的机器人Token
ALLOWED_USER_ID=你的TG账号ID

# 下载与限速
DOWNLOAD_DIR=/root/yt-dlp-telegram-bot/downloads
LIMIT_RATE=15M

# WebDAV 同步配置
WEBDAV_USER=admin
WEBDAV_PASS=你的复杂密码
```
### 3. 一键启动 / Running
```bash
# 启动 WebDAV 同步服务 (Setup WebDAV Service)
chmod +x setup_webdav.sh
./setup_webdav.sh

# 后台运行机器人 (Run Bot in background)
nohup python3 main.py > bot.log 2>&1 &
```


### 极空间/群晖同步 / NAS Sync
在 NAS (极空间/群晖) 的 外部设备/Cloud Sync 中添加 WebDAV。

地址填入 http://你的VPS_IP:8080。

输入 .env 中设置的 WebDAV 账号密码。

设置 单向同步，即可实现：发链接给TG -> VPS下载 -> NAS自动入库。


