#!/usr/bin/env bash
set -euo pipefail

# ── yt-dlp Bot 安装脚本 ─────────────────────────────────────────────────
# 支持两种模式：
#   交互式:  bash install.sh                  # 逐个提问
#   AI 式:   bash install.sh --tg-token xxx --tg-user 123 ...   # 参数直接填入
#
# 用法:
#   bash install.sh [OPTIONS]
#
# 选项:
#   --tg-token TOKEN        Telegram Bot Token
#   --tg-user USER_ID       Telegram 允许的 User ID
#   --rc-server URL         Rocket.Chat 服务器地址（默认 https://chat.akria.net）
#   --rc-user USER_ID       RC 用户 ID
#   --rc-token TOKEN        RC Personal Access Token
#   --rc-channel CHANNEL    RC 监听频道（默认 渠道监控）
#   --download-dir PATH     下载目录
#   --limit-rate RATE       限速（默认 15M）
#   --max-concurrent N      最大并发（默认 2）
#   --install-dir PATH      安装目录（默认 /opt/yt-dlp-bot）
#   --systemd               注册 systemd 服务
#   --uninstall             卸载
#   -y                      AI 模式：不确认直接安装
#   -h                      帮助

cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"

# ── 默认值 ──────────────────────────────────────────────────────────────────
INSTALL_DIR="${INSTALL_DIR:-/opt/yt-dlp-bot}"
DOWNLOAD_DIR="${DOWNLOAD_DIR:-}"
LIMIT_RATE="15M"
MAX_CONCURRENT="2"
RC_SERVER="https://chat.akria.net"
RC_CHANNEL="渠道监控"
DO_SYSTEMD=false
AI_MODE=false
DO_UNINSTALL=false

# ── 解析参数 ────────────────────────────────────────────────────────────────
TG_TOKEN=""
TG_USER=""
RC_USER_ID=""
RC_TOKEN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tg-token) TG_TOKEN="$2"; shift 2 ;;
        --tg-user) TG_USER="$2"; shift 2 ;;
        --rc-server) RC_SERVER="$2"; shift 2 ;;
        --rc-user) RC_USER_ID="$2"; shift 2 ;;
        --rc-token) RC_TOKEN="$2"; shift 2 ;;
        --rc-channel) RC_CHANNEL="$2"; shift 2 ;;
        --download-dir) DOWNLOAD_DIR="$2"; shift 2 ;;
        --limit-rate) LIMIT_RATE="$2"; shift 2 ;;
        --max-concurrent) MAX_CONCURRENT="$2"; shift 2 ;;
        --install-dir) INSTALL_DIR="$2"; shift 2 ;;
        --systemd) DO_SYSTEMD=true; shift ;;
        --uninstall) DO_UNINSTALL=true; shift ;;
        -y) AI_MODE=true; shift ;;
        -h|--help)
            sed -n '/^# ──/,/^$/p' "$0" | grep -E '^#' | sed 's/^# //;s/^#$//'
            exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# ── 卸载 ────────────────────────────────────────────────────────────────────
if $DO_UNINSTALL; then
    echo "📦 卸载 yt-dlp Bot..."
    if systemctl is-enabled yt-dlp-bot &>/dev/null 2>&1; then
        systemctl stop yt-dlp-bot 2>/dev/null || true
        systemctl disable yt-dlp-bot 2>/dev/null || true
        rm -f /etc/systemd/system/yt-dlp-bot.service
        systemctl daemon-reload
    fi
    if [ -d "$INSTALL_DIR" ]; then
        read -rp "删除 $INSTALL_DIR? (y/N): " yn
        [[ "$yn" == "y" || "$yn" == "Y" ]] && rm -rf "$INSTALL_DIR" && echo "✅ 已删除"
    fi
    echo "✅ 卸载完成"
    exit 0
fi

# ── 系统依赖 ────────────────────────────────────────────────────────────────
echo "📦 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq ffmpeg python3-pip python3-venv curl

# ── 交互式配置 ──────────────────────────────────────────────────────────────
if ! $AI_MODE; then
    echo ""
    echo "════════════════════════════════════════"
    echo "  yt-dlp Video Downloader Bot 安装"
    echo "════════════════════════════════════════"
    echo ""

    if [[ -z "$TG_TOKEN" && -z "$TG_USER" && -z "$RC_USER_ID" && -z "$RC_TOKEN" ]]; then
        echo "选择 Bot 类型："
        echo "  1) Telegram Bot"
        echo "  2) Rocket.Chat Bot"
        echo "  3) 两者都启用"
        read -rp "请输入 (1/2/3): " bot_type
        case "$bot_type" in
            1|2) ;;
            3) ;;
            *) echo "无效输入"; exit 1 ;;
        esac
    fi

    if [[ "$bot_type" == "1" || "$bot_type" == "3" || -n "$TG_TOKEN" || -n "$TG_USER" ]]; then
        [[ -z "$TG_TOKEN" ]] && read -rp "Telegram Bot Token (从 @BotFather 获取): " TG_TOKEN
        [[ -z "$TG_USER" ]] && read -rp "Telegram User ID (你的账号 ID): " TG_USER
    fi

    if [[ "$bot_type" == "2" || "$bot_type" == "3" || -n "$RC_USER_ID" || -n "$RC_TOKEN" ]]; then
        [[ -z "$RC_SERVER" ]] && read -rp "RC 服务器地址 [https://chat.akria.net]: " tmp && RC_SERVER="${tmp:-$RC_SERVER}"
        [[ -z "$RC_USER_ID" ]] && read -rp "RC 用户 ID: " RC_USER_ID
        [[ -z "$RC_TOKEN" ]] && read -rp "RC Personal Access Token: " RC_TOKEN
        [[ -z "$RC_CHANNEL" ]] && read -rp "RC 监听频道 [渠道监控]: " tmp && RC_CHANNEL="${tmp:-$RC_CHANNEL}"
    fi

    [[ -z "$DOWNLOAD_DIR" ]] && read -rp "下载目录 [$INSTALL_DIR/downloads]: " tmp && DOWNLOAD_DIR="${tmp:-$INSTALL_DIR/downloads}"
    read -rp "限速（默认 $LIMIT_RATE）: " tmp && LIMIT_RATE="${tmp:-$LIMIT_RATE}"
    read -rp "最大并发下载数（默认 $MAX_CONCURRENT）: " tmp && MAX_CONCURRENT="${tmp:-$MAX_CONCURRENT}"
    read -rp "安装目录 [$INSTALL_DIR]: " tmp && INSTALL_DIR="${tmp:-$INSTALL_DIR}"
    read -rp "注册为 systemd 服务? (Y/n): " yn
    [[ "$yn" != "n" && "$yn" != "N" ]] && DO_SYSTEMD=true
fi

# ── 写入配置 ────────────────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR"

cat > "$INSTALL_DIR/.env" <<ENVEOF
# yt-dlp Bot 配置 — 由 install.sh 自动生成
TG_TOKEN=${TG_TOKEN:-}
ALLOWED_USER_ID=${TG_USER:-0}
RC_SERVER=${RC_SERVER}
RC_USER_ID=${RC_USER_ID:-}
RC_TOKEN=${RC_TOKEN:-}
RC_CHANNEL=${RC_CHANNEL:-渠道监控}
DOWNLOAD_DIR=${DOWNLOAD_DIR:-$INSTALL_DIR/downloads}
LIMIT_RATE=${LIMIT_RATE}
MAX_CONCURRENT=${MAX_CONCURRENT}
ENVEOF

echo "✅ 配置已写入 $INSTALL_DIR/.env"

# ── 复制代码 ────────────────────────────────────────────────────────────────
echo "📂 复制代码..."
cp -r "$SCRIPT_DIR"/*.py "$SCRIPT_DIR"/*.txt "$INSTALL_DIR/" 2>/dev/null || true
# 如果脚本就在安装目录里运行，不需要复制
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    cp "$SCRIPT_DIR"/.env.example "$INSTALL_DIR/" 2>/dev/null || true
fi

# ── Python 虚拟环境 ─────────────────────────────────────────────────────────
echo "🐍 配置 Python 虚拟环境..."
cd "$INSTALL_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt
deactivate

# ── systemd 服务 ────────────────────────────────────────────────────────────
if $DO_SYSTEMD; then
    echo "🔧 注册 systemd 服务..."
    cat > /etc/systemd/system/yt-dlp-bot.service <<UNIT
[Unit]
Description=yt-dlp Video Downloader Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
ExecStart=$INSTALL_DIR/.venv/bin/python3 $INSTALL_DIR/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

    systemctl daemon-reload
    systemctl enable yt-dlp-bot
    systemctl restart yt-dlp-bot
    echo "✅ 服务已启动"
    echo "   查看日志: journalctl -u yt-dlp-bot -f"
fi

# ── 完成 ────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo "  ✅ 安装完成！"
echo "════════════════════════════════════════"
echo ""
echo "📍 安装路径: $INSTALL_DIR"
echo "📄 配置文件: $INSTALL_DIR/.env"
echo "📂 下载目录: ${DOWNLOAD_DIR:-$INSTALL_DIR/downloads}"

if ! $DO_SYSTEMD; then
    echo ""
    echo "手动启动:"
    echo "  cd $INSTALL_DIR && .venv/bin/python3 main.py"
fi

echo ""
