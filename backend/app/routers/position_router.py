from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas, auth

router = APIRouter(prefix="/api/admin/positions", tags=["admin_positions"])

@router.get("/", response_model=List[schemas.PositionOut])
def get_positions(db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin_user)):
    """获取所有已存职位列表（按名称排序）"""
    positions = db.query(models.Position).order_by(models.Position.name).all()
    return positions

@router.post("/", response_model=schemas.PositionOut)
def create_position(
    name: str,
    db: Session = Depends(get_db),
    admin: models.User = Depends(auth.get_current_admin_user)
):
    """手动添加职位（通常由用户输入自动触发）"""
    existing = db.query(models.Position).filter(models.Position.name == name).first()
    if existing:
        return existing
    new_pos = models.Position(name=name)
    db.add(new_pos)
    db.commit()
    db.refresh(new_pos)
    return new_pos