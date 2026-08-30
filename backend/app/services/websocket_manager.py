# backend/app/services/websocket_manager.py
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        # user_id -> 该用户的全部在线连接
        self.active_connections = {}
        # 在线管理员的 user_id 集合（connect 时根据 role 写入）
        self.admin_ids = set()
        # 主事件循环引用，用于从后台线程安全推送
        self._loop = None

    # ---------- 连接管理（事件循环线程内调用） ----------
    async def connect(self, user_id: int, websocket, role: str = "user"):
        await websocket.accept()
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        self.active_connections.setdefault(user_id, set()).add(websocket)
        if role == "admin":
            self.admin_ids.add(user_id)
            logger.info(f"🔗 管理员 {user_id} 已连接 WebSocket（在线管理员数: {len(self.admin_ids)}）")
        else:
            logger.info(f"🔗 用户 {user_id} 已连接 WebSocket")

    def disconnect(self, user_id: int, websocket):
        conns = self.active_connections.get(user_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                self.active_connections.pop(user_id, None)
                self.admin_ids.discard(user_id)

    # ---------- 实际发送（事件循环内执行） ----------
    async def _broadcast_admins(self, payload: dict):
        targets = []
        for uid in list(self.admin_ids):
            for ws in list(self.active_connections.get(uid, ())):
                targets.append((uid, ws))
        if not targets:
            logger.warning("⚠️ 推送失败：当前没有任何在线管理员连接（检查 connect 是否传了 role='admin'）")
            return
        dead = []
        for uid, ws in targets:
            try:
                await ws.send_text(json.dumps(payload, ensure_ascii=False, default=str))
            except Exception as e:
                logger.warning(f"推送给管理员 {uid} 失败，移除连接: {e}")
                dead.append((uid, ws))
        for uid, ws in dead:
            self.disconnect(uid, ws)
        logger.info(f"📢 已推送 [{payload.get('type')}] 给 {len(targets) - len(dead)} 个管理员连接")

    async def _send_to_user(self, user_id: int, payload: dict):
        conns = list(self.active_connections.get(user_id, ()))
        if not conns:
            logger.info(f"用户 {user_id} 不在线，跳过推送")
            return
        dead = []
        for ws in conns:
            try:
                await ws.send_text(json.dumps(payload, ensure_ascii=False, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    async def _broadcast_all(self, payload: dict):
        for uid in list(self.active_connections.keys()):
            await self._send_to_user(uid, payload)

    # ---------- 线程安全入口（供 BackgroundTasks / 后台线程调用） ----------
    def _submit(self, coro):
        if self._loop is None or self._loop.is_closed():
            logger.warning("⚠️ 事件循环不可用，无法推送WS消息")
            return
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        except Exception as e:
            logger.warning(f"WS跨线程推送失败: {e}")

    def notify_admins_threadsafe(self, payload: dict):
        logger.info(f"📢 notify_admins: type={payload.get('type')}, title={payload.get('title', '')}")
        self._submit(self._broadcast_admins(payload))

    def notify_user_threadsafe(self, user_id: int, payload: dict):
        self._submit(self._send_to_user(user_id, payload))

    def broadcast_threadsafe(self, payload: dict):
        self._submit(self._broadcast_all(payload))


websocket_manager = WebSocketManager()
