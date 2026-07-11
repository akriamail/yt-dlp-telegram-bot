#!/usr/bin/env python3
"""
yt-dlp Video Downloader Bot — Unified Entry Point

Supports Telegram and/or Rocket.Chat. Configure via .env or environment variables.
"""

import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv

import downloader as dl

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _env(key: str, default=""):
    return os.getenv(key, default)


def _env_int(key: str, default: int):
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _read_config():
    """从 .env 读取配置，返回 (config, enable_tg, enable_rc)"""
    config = dict(
        download_dir=_env("DOWNLOAD_DIR", "./downloads"),
        limit_rate=_env("LIMIT_RATE", "15M"),
        max_concurrent=_env_int("MAX_CONCURRENT", 2),
        tg_token=_env("TG_TOKEN"),
        tg_user=_env_int("ALLOWED_USER_ID", 0),
        rc_server=_env("RC_SERVER", "https://chat.akria.net"),
        rc_uid=_env("RC_USER_ID"),
        rc_token=_env("RC_TOKEN"),
        rc_channel=_env("RC_CHANNEL", "渠道监控"),
    )
    enable_tg = bool(config["tg_token"] and config["tg_user"])
    enable_rc = bool(config["rc_uid"] and config["rc_token"])

    if not enable_tg and not enable_rc:
        logger.error("未检测到任何 Bot 配置！")
        logger.error("   Telegram: 设置 TG_TOKEN + ALLOWED_USER_ID")
        logger.error("   Rocket.Chat: 设置 RC_USER_ID + RC_TOKEN")
        sys.exit(1)

    return config, enable_tg, enable_rc


# ── 共享事件循环模式（RC 参与时使用）───────────────────────────────────────────

async def amain(config: dict, enable_tg: bool, enable_rc: bool):
    """在共享事件循环中运行所有 Bot task。收到 CancelledError 时优雅关闭。"""
    tg_bot = None
    rc_bot = None

    if enable_rc:
        from bot_rocketchat import RocketChatBot
        rc_bot = RocketChatBot(
            server_url=config["rc_server"],
            user_id=config["rc_uid"],
            token=config["rc_token"],
            channel=config["rc_channel"],
            download_dir=config["download_dir"],
            limit_rate=config["limit_rate"],
            max_concurrent=config["max_concurrent"],
        )

    if enable_tg:
        from bot_telegram import TelegramBot
        tg_bot = TelegramBot(
            token=config["tg_token"],
            allowed_user_id=config["tg_user"],
            download_dir=config["download_dir"],
            limit_rate=config["limit_rate"],
        )

    tasks = []
    if rc_bot:
        tasks.append(asyncio.create_task(rc_bot.run_forever()))
    if tg_bot:
        tasks.append(asyncio.create_task(tg_bot.start_polling()))

    for name, t in zip(
        [n for n, e in [("RC", rc_bot), ("TG", tg_bot)] if e],
        tasks,
    ):
        logger.info("🚀 %s Bot 已启动（共享事件循环）", name)

    try:
        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_EXCEPTION,
        )
        for t in done:
            exc = t.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                logger.error("Bot 异常退出: %s", exc)
    except asyncio.CancelledError:
        logger.info("收到关闭信号，正在停止...")
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if tg_bot:
            await tg_bot.stop()
        if rc_bot:
            await rc_bot.shutdown()
        logger.info("Bot 已停止")


# ── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    dl.update_yt_dlp()
    config, enable_tg, enable_rc = _read_config()

    # ── TG-only: PTB 管理自己的事件循环 ──────────────────────────────────────
    if enable_tg and not enable_rc:
        from bot_telegram import TelegramBot
        bot = TelegramBot(
            token=config["tg_token"],
            allowed_user_id=config["tg_user"],
            download_dir=config["download_dir"],
            limit_rate=config["limit_rate"],
        )
        logger.info("🚀 Telegram Bot 已启动（独立模式）")
        bot.run()
        return

    # ── RC 参与：共享事件循环，信号 → cancel → 清理 ──────────────────────────
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    main_task = asyncio.ensure_future(
        amain(config, enable_tg, enable_rc), loop=loop,
    )

    # 取消主 task 而非停止 loop，让 amain() 跑完 finally 清理
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, main_task.cancel)
        except NotImplementedError:
            pass

    try:
        loop.run_until_complete(main_task)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        if not loop.is_closed():
            loop.close()


if __name__ == "__main__":
    main()
