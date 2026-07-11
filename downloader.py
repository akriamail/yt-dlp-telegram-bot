#!/usr/bin/env python3
"""
yt-dlp 下载引擎 — 被 TG/RC bot 共用
"""

import asyncio
import logging
import os
import re
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

# ── yt-dlp 自更新 ───────────────────────────────────────────────────────────
def update_yt_dlp():
    logger.info("🔄 检查 yt-dlp 更新...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"])
        logger.info("✅ yt-dlp 已更新")
    except Exception as e:
        logger.error("❌ yt-dlp 更新失败: %s", e)


# ── 链接清洗 ────────────────────────────────────────────────────────────────
def clean_url(url: str) -> str:
    """清洗链接，兼容 PH 移动端域名和 viewkey 参数"""
    # 分离 query 参数，保留 viewkey
    base = url.split("?")[0].replace("m.pornhub.com", "cn.pornhub.com")
    if "viewkey=" in url:
        vk = re.search(r"viewkey=[a-zA-Z0-9]+", url)
        if vk and "viewkey=" not in base:
            return f"https://cn.pornhub.com/view_video.php?{vk.group()}"
    return base


def build_cmd(url: str, download_dir: str, limit_rate: str) -> list[str]:
    """构建 yt-dlp 命令"""
    archive = os.path.join(download_dir, ".archive.txt")
    return [
        "yt-dlp",
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--no-playlist",
        "--socket-timeout", "60",
        "--retries", "10",
        "--limit-rate", limit_rate,
        "--download-archive", archive,
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-P", download_dir,
        "--newline",
        "--no-mtime",
        "--exec", "chmod 755 {}",
        clean_url(url),
    ]


# ── 异步下载 + 进度回调 ────────────────────────────────────────────────────
async def daily_cleanup(download_dir: str):
    """每天凌晨 3:00 清理超过 24 小时的下载文件"""
    while True:
        now = time.time()
        # 距下次凌晨 3 点的秒数
        seconds_to_3am = (86400 - (now % 86400) + 3 * 3600) % 86400
        await asyncio.sleep(seconds_to_3am)

        cutoff = time.time() - 86400
        deleted = 0
        if not os.path.isdir(download_dir):
            continue
        for f in os.listdir(download_dir):
            path = os.path.join(download_dir, f)
            if not os.path.isfile(path) or f.startswith("."):
                continue
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    deleted += 1
                    logger.info("🗑️ 每日清理: %s", f)
            except Exception as e:
                logger.warning("清理失败 %s: %s", f, e)
        if deleted:
            logger.info("✅ 每日清理 %d 个文件", deleted)


async def run_download(
    url: str,
    download_dir: str,
    limit_rate: str,
    on_progress=None,
    on_done=None,
    on_error=None,
):
    """
    执行 yt-dlp 下载

    回调签名:
        on_progress(percent: str, speed: str, eta: str)
        on_done()
        on_error(stderr: str)
    """
    cmd = build_cmd(url, download_dir, limit_rate)
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    last_update = 0.0
    captured_stderr = []

    async def read_stderr():
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            captured_stderr.append(line.decode(errors="replace"))

    stderr_task = asyncio.create_task(read_stderr())

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        text = line.decode(errors="replace").strip()

        m = re.search(
            r"\[download\]\s+([\d.]+)%.*?at\s+([\d.]+\w+/s)\s+ETA\s+([\d:]+)",
            text,
        )
        if m:
            now = time.time()
            if now - last_update >= 10:
                last_update = now
                if on_progress:
                    on_progress(m.group(1), m.group(2), m.group(3))

    await process.wait()
    await stderr_task

    if process.returncode == 0:
        logger.info("✅ 下载成功: %s", url)
        if on_done:
            await on_done()
    else:
        err_text = "".join(captured_stderr)[-500:]
        logger.error("❌ 下载失败: %s | %s", url, err_text)
        if on_error:
            await on_error(err_text)
