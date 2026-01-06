import asyncio
import os
import re
import time
import logging
import subprocess
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# 1. 初始化日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. 加载配置
load_dotenv()
TOKEN = os.getenv("TG_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", 0))
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")
LIMIT_RATE = os.getenv("LIMIT_RATE", "15M")

# 确保下载目录存在
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
    logger.info(f"创建下载目录: {DOWNLOAD_DIR}")

def update_yt_dlp():
    """启动时自动检查并更新 yt-dlp"""
    logger.info("🔄 正在检查 yt-dlp 更新...")
    try:
        # 使用 pip 升级 yt-dlp
        subprocess.check_call(["pip3", "install", "-U", "yt-dlp"])
        logger.info("✅ yt-dlp 已是最新版本")
    except Exception as e:
        logger.error(f"❌ 自动更新 yt-dlp 失败: {e}")

async def download_task(url, update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("📡 任务已接收，正在初始化解析...")
    
    # 链接清洗 (兼容移动端域名及 viewkey 参数)
    clean_url = url.split('?')[0].replace('m.pornhub.com', 'cn.pornhub.com')
    if "viewkey=" not in clean_url and "viewkey=" in url:
        vk_match = re.search(r'viewkey=[a-zA-Z0-9]+', url)
        if vk_match:
            clean_url = f"https://cn.pornhub.com/view_video.php?{vk_match.group()}"

    cmd = [
        "stdbuf", "-oL", "yt-dlp",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--no-playlist",
        "--socket-timeout", "60",
        "--retries", "10",
        "--limit-rate", LIMIT_RATE,
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-P", DOWNLOAD_DIR,
        "--newline",
        "--no-mtime",
        "--exec", "chmod 755 {}",
        clean_url
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    last_update_time = 0
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        
        text_line = line.decode().strip()
        progress_match = re.search(r'\[download\]\s+(\d+\.\d+)%.*?at\s+([\d\.]+\w+/s)\s+ETA\s+([\d:]+)', text_line)
        
        if progress_match:
            now = time.time()
            if now - last_update_time >= 10:
                percent, speed, eta = progress_match.groups()
                progress_text = (
                    f"⏳ 正在下载中...\n\n"
                    f"📊 进度: {percent}%\n"
                    f"🚀 速度: {speed}\n"
                    f"⏱️ 剩余: {eta}"
                )
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=status_msg.message_id,
                        text=progress_text
                    )
                    last_update_time = now
                except:
                    pass

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        logger.info(f"下载成功: {url}")
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text="✅ 下载完成！文件已存入本地目录。"
        )
    else:
        logger.error(f"下载失败: {stderr.decode()}")
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text="❌ 下载失败，请检查链接或稍后重试。"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    text = update.message.text.strip()
    if text.startswith('http'):
        asyncio.create_task(download_task(text, update, context))

if __name__ == '__main__':
    # 执行启动自更新
    update_yt_dlp()

    if not TOKEN:
        print("❌ 错误: 请在 .env 文件中设置 TG_TOKEN")
        exit(1)

    print("🚀 视频下载机器人已启动并守候中...")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
