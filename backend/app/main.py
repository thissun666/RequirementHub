# ===== backend/app/main.py =====
import time
import os
import sys
import pkgutil
import importlib
from fastapi.routing import APIRoute

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .database import Base, engine, SessionLocal
from . import models, auth
from .config import UPLOAD_DIR
from . import routers as routers_pkg
from .routers.websocket_router import handle_websocket

# ★★★ 关键修复：静态导入全部路由模块 ★★★
# PyInstaller 只保证打包"静态 import"到的模块；--collect-submodules 不可靠。
# websocket_router 能进exe正是因为它被静态导入了。以后新增路由文件，
# 必须同步加进下面的 import 列表，否则 dev 正常、打包后缺失。
from .routers import (
    auth_router,
    conversation_router,
    knowledge_router,
    position_router,
    report_router,
    requirement_router,
    settings_router,
    user_ai_router,
    user_router,
)

app = FastAPI(title="需求中枢")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 内网开发用；上生产改为 ["http://你的域名"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 中间件1：API路径斜杠自适应 ----------
# ---------- 中间件1：API路径斜杠自适应（方法感知版） ----------
@app.middleware("http")
async def api_slash_redirect(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api"):
        method = request.method

        def _hit(p: str) -> bool:
            # 该路径上是否存在"接受当前HTTP方法"的路由
            return any(
                isinstance(r, APIRoute) and r.path == p
                and (r.methods is None or method in r.methods)
                for r in app.routes
            )

        if not _hit(path):
            if _hit(path + "/"):
                request.scope["path"] = path + "/"
            elif path.endswith("/") and _hit(path.rstrip("/")):
                request.scope["path"] = path.rstrip("/")
    return await call_next(request)

# ---------- 中间件2：安全加固 ----------
_login_attempts: dict = {}

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    path = request.url.path
    now = time.time()
    if path.startswith("/api/auth/login"):
        win = _login_attempts.setdefault(ip, [])
        while win and now - win[0] > 60:
            win.pop(0)
        if len(win) >= 10:
            return JSONResponse({"detail": "尝试过于频繁，请1分钟后再试"}, status_code=429)
        win.append(now)
    if path.startswith("/uploads/"):
        ref = request.headers.get("referer", "")
        host = request.headers.get("host", "")
        if ref and host and host not in ref:
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    if path.startswith("/uploads/"):
        resp.headers.setdefault("Cache-Control", "public, max-age=2592000")
    elif path.startswith(("/js/", "/css/")):
        resp.headers.setdefault("Cache-Control", "no-cache")
    elif path.endswith(".html"):
        resp.headers.setdefault("Cache-Control", "no-cache")
    return resp

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/login.html")

# ---------- 路由注册 ----------
def _auto_register_routers():
    seen = set()
    registered = 0

    if getattr(sys, "frozen", False):
        # exe：直接用顶部静态导入的模块对象（它们保证在包里）
        pairs = [
            ("auth_router", auth_router),
            ("conversation_router", conversation_router),
            ("knowledge_router", knowledge_router),
            ("position_router", position_router),
            ("report_router", report_router),
            ("requirement_router", requirement_router),
            ("settings_router", settings_router),
            ("user_ai_router", user_ai_router),
            ("user_router", user_router),
        ]
    else:
        # dev：保持自动扫描
        pairs = []
        for mod_info in pkgutil.iter_modules(routers_pkg.__path__):
            name = mod_info.name
            if name.startswith("_") or name == "websocket_router":
                continue
            try:
                mod = importlib.import_module(f".{name}", package=routers_pkg.__name__)
            except Exception as e:
                print(f"⚠️ 跳过路由模块 routers/{name}.py: {e}")
                continue
            pairs.append((name, mod))

    for name, mod in pairs:
        found = [(n, a) for n, a in vars(mod).items() if isinstance(a, APIRouter)]
        if not found:
            continue
        chosen = [x for x in found if x[0] == "router"] or found
        for attr_name, attr in chosen:
            if id(attr) in seen:
                continue
            seen.add(id(attr))
            app.include_router(attr)
            registered += 1
            print(f"✅ 注册路由: routers/{name}.py → {attr.prefix or '/'} ({len(attr.routes)} 条)")
    if registered == 0:
        print("❌ 未发现任何路由！请检查 backend/app/routers 目录")

_auto_register_routers()

# ---------- WebSocket 实时推送 ----------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    db = SessionLocal()
    try:
        await handle_websocket(websocket, db, token)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"⚠️ WebSocket异常: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        db.close()

# ---------- 启动：建表 + 幂等迁移 + 种子管理员 ----------
def run_migrations():
    db = SessionLocal()
    try:
        alters = [
            "ALTER TABLE users ADD COLUMN position VARCHAR(100)",
            "ALTER TABLE users ADD COLUMN preferred_model VARCHAR(100)",
            "ALTER TABLE conversations ADD COLUMN mode VARCHAR(20) DEFAULT 'requirement'",
            "ALTER TABLE conversations ADD COLUMN title VARCHAR(100)",
            "ALTER TABLE messages ADD COLUMN attachment_name VARCHAR(255)",
            "ALTER TABLE messages ADD COLUMN attachment_path VARCHAR(500)",
            "ALTER TABLE messages ADD COLUMN is_private BOOLEAN DEFAULT 0",
            "ALTER TABLE conversations ADD COLUMN is_hidden BOOLEAN DEFAULT 0",
            "ALTER TABLE knowledge_items ADD COLUMN content TEXT",
            "ALTER TABLE knowledge_items ADD COLUMN embedding TEXT",
            "ALTER TABLE knowledge_items ADD COLUMN source_name VARCHAR(120) DEFAULT ''",
        ]
        for sql in alters:
            try:
                db.execute(text(sql))
                db.commit()
                print(f"✅ 迁移完成: {sql}")
            except Exception:
                db.rollback()
    finally:
        db.close()

def seed_admin():
    db = SessionLocal()
    try:
        if not db.query(models.User).filter(models.User.username == "admin").first():
            db.add(models.User(
                username="admin",
                password_hash=auth.get_password_hash("admin123"),
                role=models.UserRole.ADMIN,
            ))
            db.commit()
            print("✅ 已创建默认管理员 admin/admin123")
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    run_migrations()
    seed_admin()
    print("🚀 需求中枢启动完成")

# ---------- 静态托管（必须放在所有路由之后） ----------
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

FRONTEND_DIR = Path(os.environ.get("REQHUB_FRONTEND_DIR")
                    or (Path(__file__).resolve().parents[2] / "frontend"))
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
print("✅ 前端页面已托管")
print("✅ 附件目录已挂载 /uploads")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
