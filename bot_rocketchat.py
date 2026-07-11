#!/usr/bin/env python3
"""
Rocket.Chat Bot 接入层 — 通过 WebSocket RealTime API 与 RC 交互
"""

import asyncio
import json
import logging
import re
import re

import httpx
import websockets

import downloader as dl

logger = logging.getLogger(__name__)


def _http_to_ws(url: str) -> str:
    """http(s):// → ws(s):// 协议转换"""
    return re.sub(r"^http", "ws", url)


class RocketChatBot:
    def __init__(self, server_url: str, user_id: str, token: str,
                 channel: str, download_dir: str, limit_rate: str,
                 max_concurrent: int = 2):
        self.server_url = server_url.rstrip("/")
        self.user_id = user_id
        self.token = token
        self.channel = channel
        self.download_dir = download_dir
        self.limit_rate = limit_rate
        self.sem = asyncio.Semaphore(max_concurrent)

        self._http = httpx.AsyncClient(
            base_url=self.server_url,
            timeout=httpx.Timeout(15.0),
            headers={"X-Auth-Token": token, "X-User-Id": user_id},
        )
        self._room_id = None

    # ── REST 消息（带日志）─────────────────────────────────────────────────────
    async def send_msg(self, room_id: str, text: str) -> str | None:
        """发送消息，失败时记录警告并返回 None"""
        try:
            r = await self._http.post(
                "/api/v1/chat.sendMessage",
                json={"message": {"rid": room_id, "msg": text}},
            )
            data = r.json()
            if r.is_success and data.get("success"):
                return data["message"]["_id"]
            logger.warning("send_msg 失败: HTTP %s %s", r.status_code, data.get("error", ""))
        except Exception as e:
            logger.warning("send_msg 异常: %s", e)
        return None

    async def update_msg(self, room_id: str, msg_id: str, text: str):
        """更新消息，失败时记录警告"""
        try:
            r = await self._http.post(
                "/api/v1/chat.update",
                json={"roomId": room_id, "msgId": msg_id, "text": text},
            )
            data = r.json()
            if not (r.is_success and data.get("success")):
                logger.warning("update_msg 失败: HTTP %s %s", r.status_code, data.get("error", ""))
        except Exception as e:
            logger.warning("update_msg 异常: %s", e)

    # ── 房间解析 ──────────────────────────────────────────────────────────────
    async def _resolve_room(self, name: str) -> str:
        """解析频道名/群组名/用户名/room_id → room_id。"""
        key = name.lstrip("#")
        # 已经是 room_id（24 位 hex）
        if re.match(r"^[a-f0-9]{24}$", key, re.I):
            return key
        # DM：用 spotlight 搜索用户，找到后创建或获取现有 IM room
        r = await self._http.get("/api/v1/spotlight", params={"query": key})
        users = r.json().get("users", [])
        if users:
            r = await self._http.post("/api/v1/im.create", json={"username": users[0]["username"]})
            room = r.json().get("room", {})
            if room:
                return room["_id"]
        # 公开频道 / 私有群组
        for endpoint in ("channels.info", "groups.info"):
            r = await self._http.get(f"/api/v1/{endpoint}", params={"roomName": key})
            data = r.json()
            ep = endpoint.split(".")[0]
            if data.get("success") and data.get(ep):
                return data[ep]["_id"]
        raise ValueError(f"Cannot resolve room: {name}")

    # ── 下载任务 ──────────────────────────────────────────────────────────────
    async def _download(self, url: str, room_id: str):
        async with self.sem:
            mid = await self.send_msg(room_id, "📡 正在解析链接...")
            if not mid:
                logger.warning("无法向频道发送消息（mid=None），下载仍将继续")
                await dl.run_download(url=url, download_dir=self.download_dir, limit_rate=self.limit_rate)
                return

            def on_progress(pct, speed, eta):
                asyncio.ensure_future(self.update_msg(room_id, mid,
                    f"⏳ 下载中…\n📊 {pct}%\n🚀 {speed}\n⏱️ 剩余 {eta}"))

            async def on_done():
                await self.update_msg(room_id, mid, "✅ 下载完成！")

            async def on_error(err):
                await self.update_msg(room_id, mid, f"❌ 下载失败\n`{err.strip()}`")

            await dl.run_download(
                url=url, download_dir=self.download_dir, limit_rate=self.limit_rate,
                on_progress=on_progress, on_done=on_done, on_error=on_error,
            )

    # ── WS 主循环 ────────────────────────────────────────────────────────────
    async def run_forever(self):
        ws_url = _http_to_ws(self.server_url) + "/websocket"
        self._room_id = await self._resolve_room(self.channel)
        logger.info("Room %s → %s | WS: %s", self.channel, self._room_id, ws_url)

        while True:
            try:
                async with websockets.connect(
                    ws_url, ping_interval=25, ping_timeout=10, max_size=2**20
                ) as ws:

                    # connect
                    await ws.send(json.dumps({
                        "msg": "connect", "version": "1",
                        "support": ["1", "pre2", "pre1"],
                    }))
                    conn = json.loads(await ws.recv())
                    logger.info("DDP session: %s", conn.get("session", ""))

                    # login via REST → resume token (more reliable than PAT direct)
                    r = await self._http.post("/api/v1/login", json={"resume": self.token})
                    data = r.json()
                    auth_token = data.get("data", {}).get("authToken", "")
                    if not auth_token:
                        logger.error("REST 登录失败: %s", data.get("error", "unknown"))
                        return

                    await ws.send(json.dumps({
                        "msg": "method", "method": "login",
                        "params": [{"resume": auth_token}], "id": "1",
                    }))

                    while True:
                        msg = json.loads(await ws.recv())
                        if msg.get("msg") == "result" and msg.get("id") == "1":
                            if msg.get("error"):
                                logger.error("WS 登录失败: %s", msg["error"])
                                return
                            logger.info("RC login OK")
                            break

                    # subscribe
                    await ws.send(json.dumps({
                        "msg": "sub", "id": "sub1", "name": "stream-room-messages",
                        "params": [self._room_id, {"useCollection": False, "args": []}],
                    }))

                    while True:
                        msg = json.loads(await ws.recv())
                        if msg.get("msg") == "ready" and "sub1" in msg.get("subs", []):
                            logger.info("✅ Subscribed %s", self.channel)
                            break

                    # message loop
                    async for raw in ws:
                        data = json.loads(raw)

                        if data.get("msg") == "ping":
                            pong = {"msg": "pong"}
                            if "id" in data:
                                pong["id"] = data["id"]
                            await ws.send(json.dumps(pong))
                            continue

                        if data.get("msg") != "changed" or not data.get("fields", {}).get("args"):
                            continue

                        for arg in data["fields"]["args"]:
                            m = arg if isinstance(arg, dict) else arg[0]
                            text = (m.get("msg") or "").strip()
                            sender = (m.get("u") or {}).get("username", "")

                            if sender.lower() == "clara" or "tmid" in m:
                                continue

                            urls = [w for w in text.split() if w.startswith("http")]
                            for u in urls:
                                logger.info("📥 %s from @%s", u, sender)
                                asyncio.create_task(self._download(u, self._room_id))

            except asyncio.CancelledError:
                raise
            except websockets.ConnectionClosed:
                logger.warning("WS disconnected, reconnecting in 5s")
                await asyncio.sleep(5)
            except Exception:
                logger.exception("RC bot error, retry in 15s")
                await asyncio.sleep(15)

    async def shutdown(self):
        await self._http.aclose()
