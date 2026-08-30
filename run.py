# run.py —— 开发与打包统一入口
import os
import sys
from pathlib import Path

# 打包后运行时：把工作目录切到exe旁边（数据库/上传文件都落在这里，便于备份迁移）
if getattr(sys, "frozen", False):
    os.chdir(Path(sys.executable).parent)
    os.environ["REQHUB_FRONTEND_DIR"] = str(Path(sys._MEIPASS) / "frontend")

import uvicorn
from backend.app.main import app

def _open_browser():
    import threading, webbrowser
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8000")).start()

if __name__ == "__main__":
    _open_browser()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
