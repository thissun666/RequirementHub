# backend/app/routers/websocket_router.py
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from .. import auth, models
from ..services.websocket_manager import websocket_manager


async def handle_websocket(websocket: WebSocket, db: Session, token: str = None):
    try:
        payload = auth.decode_access_token(token)
        if not payload:
            await websocket.close(code=1008)
            return
        user_id = int(payload.get("sub"))
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1008)
        return

    # ★ 关键修复：把角色传给 manager。不传的话管理员进不了 admin_ids，
    #   notify_admins_threadsafe 的广播永远发不出去
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    await websocket_manager.connect(user_id, websocket, role=role_str)

    try:
        while True:
            data = await websocket.receive_text()
            pass
    except WebSocketDisconnect:
        websocket_manager.disconnect(user_id, websocket)
