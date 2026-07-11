#!/usr/bin/env python3
"""
Telegram Bot 接入层 — 通过 python-telegram-bot 与 TG 交互

双模式：
  - run()：作为独立入口（TG-only），内部管理事件循环
  - start_polling() + stop()：在共享事件循环中运行（TG+RC 双启动）
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters

import downloader as dl

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str, allowed_user_id: int,
                 download_dir: str, limit_rate: str):
        self.token = token
        self.allowed_user_id = allowed_user_id
        self.download_dir = download_dir
        self.limit_rate = limit_rate
        self._app = None

    async def handle_message(self, update: Update, _context):
        if update.effective_user.id != self.allowed_user_id:
            return
        text = update.message.text.strip()
        if not text.startswith("http"):
            return

        status_msg = await update.message.reply_text("📡 任务已接收，正在初始化解析...")

        def on_progress(pct, speed, eta):
            text = f"⏳ 正在下载中…\n\n📊 进度: {pct}%\n🚀 速度: {speed}\n⏱️ 剩余: {eta}"
            try:
                asyncio.ensure_future(
                    _context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=status_msg.message_id,
                        text=text,
                    )
                )
            except Exception:
                pass

        async def on_done():
            nonlocal status_msg
            status_msg = await _context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="✅ 下载完成！文件已存入本地目录。",
            )

        async def on_error(err):
            nonlocal status_msg
            status_msg = await _context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=f"❌ 下载失败，请检查链接后重试。\n`{err.strip()}`",
            )

        await dl.run_download(
            url=text,
            download_dir=self.download_dir,
            limit_rate=self.limit_rate,
            on_progress=on_progress,
            on_done=on_done,
            on_error=on_error,
        )

    # ── 共享事件循环模式 ─────────────────────────────────────────────────────
    async def start_polling(self):
        """在已运行的 asyncio 事件循环中启动 TG polling"""
        self._app = ApplicationBuilder().token(self.token).build()
        self._app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        )
        await self._app.initialize()
        await self._app.updater.start_polling()
        await self._app.start()
        logger.info("🤖 Telegram Bot 已启动（共享事件循环）")

    async def stop(self):
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("🤖 Telegram Bot 已停止")

    # ── TG-only 模式 ────────────────────────────────────────────────────────
    def run(self):
        """同步入口，内部创建事件循环（仅 TG-only 时使用）"""
        self._app = ApplicationBuilder().token(self.token).build()
        self._app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        )
        logger.info("🤖 Telegram Bot 已启动（独立模式）")
        self._app.run_polling()
