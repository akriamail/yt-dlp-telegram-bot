#!/usr/bin/env python3
"""
Cookie Manager — 自动维护 X/Twitter cookies。

使用 twikit 库登录 X，导出 cookies 供 yt-dlp 使用。
启动时检查 cookies 有效期，过期自动续期。
"""

import logging
import os
import time

logger = logging.getLogger(__name__)

COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".x_cookies.json")


def _is_valid() -> bool:
    """检查 cookie 文件是否存在且未过期"""
    if not os.path.isfile(COOKIE_FILE):
        return False
    # twikit 导出的 json 格式，简单检查文件非空
    try:
        age = time.time() - os.path.getmtime(COOKIE_FILE)
        if age > 604800:  # 7 天强制刷新
            logger.info("X cookie 已超过 7 天，需刷新")
            return False
        return True
    except Exception:
        return False


async def _do_login(username: str, password: str) -> bool:
    """用 twikit 登录 X 并导出 cookies"""
    try:
        from twikit import Client
        client = Client("en-US")
        await client.login(auth_info_1=username, password=password)
        client.save_cookies(COOKIE_FILE)
        logger.info("✅ X 登录成功，cookie 已保存")
        return True
    except Exception as e:
        logger.error("❌ X 登录失败: %s", e)
        return False


async def ensure_cookies() -> str | None:
    """
    确保 X cookie 有效，返回 cookie 文件路径。
    自动处理过期重新登录。返回 None 表示未配置或登录失败。
    """
    from dotenv import load_dotenv
    load_dotenv()

    x_user = os.getenv("X_USERNAME", "")
    x_pass = os.getenv("X_PASSWORD", "")

    if not x_user or not x_pass:
        return None

    if _is_valid():
        return COOKIE_FILE

    logger.info("X cookie 过期或不存在，尝试自动登录...")
    if await _do_login(x_user, x_pass):
        return COOKIE_FILE

    logger.warning("X 自动登录失败，需手动检查账号密码")
    return None


def init_sync() -> str | None:
    """同步入口：在新线程中运行 ensure_cookies。"""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(ensure_cookies())
    finally:
        loop.close()


async def refresh():
    """手动触发 cookie 刷新（可定时调用）"""
    from dotenv import load_dotenv
    load_dotenv()

    x_user = os.getenv("X_USERNAME", "")
    x_pass = os.getenv("X_PASSWORD", "")
    if x_user and x_pass:
        await _do_login(x_user, x_pass)
