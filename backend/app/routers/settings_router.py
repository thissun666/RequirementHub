from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..config import settings, ENV_PATH
from .. import auth, models
from dotenv import set_key
from ..services.llm_service import llm_service

import os
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

class ModelSettings(BaseModel):
    provider: str
    api_key: str
    model: str
    base_url: str

@router.get("/model")
def get_model_settings(current_user: models.User = Depends(auth.get_current_active_user)):
    # 返回当前配置（脱敏）
    return {
        "provider": settings.AI_PROVIDER,
        "model": settings.AI_MODEL,
        "base_url": settings.AI_BASE_URL,
        "api_key": "***" + settings.AI_API_KEY[-4:] if len(settings.AI_API_KEY) > 4 else "***",
        "models": [m for m in settings.AI_MODELS_HISTORY.split(",") if m]
    }
@router.get("/models")
def list_available_models(current_user: models.User = Depends(auth.get_current_active_user)):
    """所有登录用户可读：子节点下拉切换用"""
    return {"models": [m for m in settings.AI_MODELS_HISTORY.split(",") if m],
            "current": settings.AI_MODEL}



@router.api_route("/model", methods=["POST", "PUT"])
def update_model_settings(
    new_settings: ModelSettings,
    current_user: models.User = Depends(auth.get_current_admin_user)  # 仅父节点可修改
):
    # 更新 .env 文件（或内存中），这里简单演示直接修改内存中的 settings 对象
    # 实际项目中建议持久化到数据库或 .env 文件，这里仅演示
        # 1) API Key 保护：空值或掩码(***)一律沿用旧 key，避免前端回显把假值存进去
    new_key = settings.AI_API_KEY
    submitted_key = (new_settings.api_key or "").strip()
    if submitted_key and not submitted_key.startswith("***"):
        new_key = submitted_key

    # 2) 更新内存配置
    settings.AI_PROVIDER = new_settings.provider.strip()
    settings.AI_MODEL    = new_settings.model.strip()
    settings.AI_BASE_URL = new_settings.base_url.strip().rstrip('/')
    settings.AI_API_KEY  = new_key

    # 3) ★ 热更新正在运行的 LLM 单例，不用重启后端立即生效
    llm_service.configure(provider=settings.AI_PROVIDER,
                          api_key=settings.AI_API_KEY,
                          model=settings.AI_MODEL,
                          base_url=settings.AI_BASE_URL)

    # 4) ★ 写回 backend/.env 持久化，重启后仍在
    for k, v in (("AI_PROVIDER", settings.AI_PROVIDER),
                 ("AI_API_KEY",  settings.AI_API_KEY),
                 ("AI_MODEL",    settings.AI_MODEL),
                 ("AI_BASE_URL", settings.AI_BASE_URL)):
        try:
            set_key(str(ENV_PATH), k, v)
        except Exception as e:
            logger.error(f"⚠️ 写入 .env 失败({k}): {e}")
       
    if settings.AI_MODEL and settings.AI_MODEL not in settings.AI_MODELS_HISTORY.split(","):
        settings.AI_MODELS_HISTORY = (settings.AI_MODELS_HISTORY.rstrip(",") + "," + settings.AI_MODEL).lstrip(",")
        try:
            set_key(str(ENV_PATH), "AI_MODELS_HISTORY", settings.AI_MODELS_HISTORY)
        except Exception as e:
            logger.error(f"⚠️ 写入模型历史失败: {e}")

    return {"detail": "Settings updated"}
