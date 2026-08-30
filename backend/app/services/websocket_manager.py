from typing import Dict, Set
from datetime import datetime   # ★ 原文件缺失此导入，调用 notify_* 会直接 NameError
import asyncio
from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}  # user_id -> set of websockets
        self.admin_ids: Set[int] = set()   # ★ 新增：在线管理员集合
        self.main_loop = None              # ★ 新增：主事件循环引用，供同步路由安全投递

    # ---------- 连接管理 ----------
    async def connect(self, user_id: int, websocket: WebSocket, role: str = "user"):
        """role 参数向后兼容：老的两个参数调用依然可用"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        if role == "admin":
            self.admin_ids.add(user_id)
            print(f"🔗 管理员 {user_id} 已连接 WebSocket")

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        self.admin_ids.discard(user_id)

    async def send_personal_message(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            for ws in list(self.active_connections[user_id]):
                try:
                    await ws.send_json(message)
                except Exception:
                    self.disconnect(user_id, ws)

    async def broadcast_to_admins(self, message: dict):
        """★ 原来是空壳(pass)，现在真正实现"""
        for uid in list(self.admin_ids):
            await self.send_personal_message(uid, message)

    # ---------- 供同步路由（运行在线程池）安全调用 ----------
    def set_loop(self, loop):
        self.main_loop = loop

    def notify_admins_threadsafe(self, message: dict):
        """同步路由里调这个，内部把协程安全地投递到主事件循环"""
        if self.main_loop and self.main_loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast_to_admins(message), self.main_loop)

    # ---------- 业务通知 ----------
    async def notify_requirement_updated(self, user_id: int, requirement_id: int, action: str = "updated"):
        await self.send_personal_message(user_id, {
            "type": "requirement_update",
            "action": action,
            "requirement_id": requirement_id,
            "timestamp": str(datetime.utcnow())
        })

    async def notify_new_message(self, user_id: int, conversation_id: str, message: dict):
        await self.send_personal_message(user_id, {
            "type": "new_message",
            "conversation_id": conversation_id,
            "message": message,
            "timestamp": str(datetime.utcnow())
        })


websocket_manager = WebSocketManager()
