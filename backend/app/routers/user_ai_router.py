# ===== 子节点个人专属AI配置（仅本人生效）=====
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, auth
from ..services.user_llm_service import user_llm_service, DEFAULT_BASES

router = APIRouter(prefix="/api/my-ai", tags=["my_ai"])


def _mask(key: str) -> str:
    if not key:
        return ""
    return key[:3] + "****" + key[-4:] if len(key) > 8 else "****"


@router.get("/")
def get_my_ai(db: Session = Depends(get_db), u: models.User = Depends(auth.get_current_active_user)):
    cfg = db.query(models.UserAIConfig).filter(models.UserAIConfig.user_id == u.id).first()
    if not cfg:
        return {"configured": False, "provider": "zhipu", "model": "", "base_url": "", "api_key": ""}
    return {"configured": True, "provider": cfg.provider, "model": cfg.model,
            "base_url": cfg.base_url, "api_key": _mask(cfg.api_key)}


@router.put("/")
def set_my_ai(data: dict, db: Session = Depends(get_db), u: models.User = Depends(auth.get_current_active_user)):
    provider = (data.get("provider") or "zhipu").strip()
    if provider not in DEFAULT_BASES:
        raise HTTPException(status_code=400, detail="不支持的提供商")
    base_url = (data.get("base_url") or "").strip().rstrip("/")
    if provider == "custom" and not base_url:
        raise HTTPException(status_code=400, detail="自定义提供商必须填写 Base URL")
    model = (data.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    api_key = (data.get("api_key") or "").strip()
    cfg = db.query(models.UserAIConfig).filter(models.UserAIConfig.user_id == u.id).first()
    if not cfg:
        cfg = models.UserAIConfig(user_id=u.id)
        db.add(cfg)
    # 掩码Key（含*号）= 未修改，沿用旧值，避免回显污染
    if api_key and "*" not in api_key:
        cfg.api_key = api_key
    cfg.provider = provider
    cfg.model = model[:100]
    cfg.base_url = base_url or DEFAULT_BASES[provider]
    cfg.updated_at = datetime.utcnow()
    db.commit()
    return {"configured": True, "provider": cfg.provider,
            "model": cfg.model, "base_url": cfg.base_url, "api_key": _mask(cfg.api_key)}

@router.delete("/")
def reset_my_ai(db: Session = Depends(get_db), u: models.User = Depends(auth.get_current_active_user)):
    db.query(models.UserAIConfig).filter(models.UserAIConfig.user_id == u.id).delete()
    db.commit()
    return {"configured": False}


@router.post("/test")
def test_my_ai(data: dict, db: Session = Depends(get_db), u: models.User = Depends(auth.get_current_active_user)):
    """用表单当前值实测连通性；Key为掩码时自动取已存Key"""
    provider = (data.get("provider") or "zhipu").strip()
    model = (data.get("model") or "").strip()
    key = (data.get("api_key") or "").strip()
    base = (data.get("base_url") or "").strip().rstrip("/")
    if "*" in key:
        cfg = db.query(models.UserAIConfig).filter(models.UserAIConfig.user_id == u.id).first()
        key = (cfg.api_key if cfg else "") or ""
    if not model:
        return {"ok": False, "error": "请先填写模型名称"}
    reply = user_llm_service.chat_completion(
        [{"role": "user", "content": '请只回复两个字：成功'}],
        provider=provider, api_key=key, model=model,
        base_url=base or DEFAULT_BASES.get(provider, ""), temperature=0.1)
    if reply:
        return {"ok": True, "reply": reply[:30]}
    return {"ok": False, "error": "调用失败：请检查Key、模型名称、Base URL或网络"}
