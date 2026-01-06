#!/bin/bash

# 自动获取当前目录下的 .env 配置
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "❌ 错误: 未找到 .env 文件，请先配置环境。"
    exit 1
fi

PORT=8080
USER=${WEBDAV_USER:-"admin"}
PASS=${WEBDAV_PASS}
SYNC_DIR=${DOWNLOAD_DIR:-"/root/yt-dlp-telegram-bot/downloads"}

if [ -z "$PASS" ]; then
    echo "❌ 错误: .env 中未设置 WEBDAV_PASS"
    exit 1
fi

echo "🌐 正在从 .env 读取配置并安装 WebDAV..."

# 1. 安装 rclone
if ! command -v rclone &> /dev/null; then
    sudo apt update && sudo apt install -y rclone
fi

# 2. 创建系统服务（不再硬编码密码，而是通过环境变量或直接写入服务）
cat <<EOF | sudo tee /etc/systemd/system/rclone-webdav.service
[Unit]
Description=Rclone WebDAV Service for NAS Sync
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/rclone serve webdav $SYNC_DIR --addr :$PORT --user $USER --pass $PASS
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# 3. 启动服务
sudo systemctl daemon-reload
sudo systemctl enable rclone-webdav.service
sudo systemctl restart rclone-webdav.service

echo "-----------------------------------------------"
echo "✅ WebDAV 服务已安全启动！"
echo "📍 地址: http://你的服务器IP:$PORT"
echo "👤 账号: $USER"
echo "🔐 密码: (已从 .env 加载，未在脚本中硬编码)"
echo "-----------------------------------------------"
