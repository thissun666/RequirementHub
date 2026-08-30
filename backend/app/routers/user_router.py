from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas, auth

router = APIRouter(prefix="/api/admin/users", tags=["admin_users"])

def sync_position(db: Session, position_name: str):
    """同步职位到 positions 表"""
    if not position_name:
        return
    existing = db.query(models.Position).filter(models.Position.name == position_name).first()
    if not existing:
        new_pos = models.Position(name=position_name)
        db.add(new_pos)
        db.commit()

@router.get("/", response_model=List[schemas.UserOut])
def list_users(db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin_user)):
    users = db.query(models.User).filter(models.User.role == models.UserRole.USER).all()
    return users

@router.post("/", response_model=schemas.UserOut)
def create_user(user_data: schemas.UserCreate, db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin_user)):
    existing = db.query(models.User).filter(models.User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed = auth.get_password_hash(user_data.password)
    new_user = models.User(
        username=user_data.username,
        password_hash=hashed,
        role=user_data.role,
        department=user_data.department,
        position=user_data.position  # 新增
    )
    db.add(new_user)
    db.flush()  # 获取ID
    if user_data.position:
        sync_position(db, user_data.position)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: int, user_data: schemas.UserUpdate, db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user_data.username:
        existing = db.query(models.User).filter(models.User.username == user_data.username).first()
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = user_data.username
    # ★ 关键：None 和 "" 都视为"不修改密码"（编辑时留空不会覆盖原密码）
    if user_data.password:
        user.password_hash = auth.get_password_hash(user_data.password)
    if user_data.department:
        user.department = user_data.department
    if user_data.position:
        user.position = user_data.position
        sync_position(db, user_data.position)
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin_user),
):
    """删除子节点用户及其全部对话/消息/需求（绕过ORM级联置NULL的坑）"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == models.UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="不能删除管理员账号")

    # 1) 先删该用户所有对话的消息
    conv_ids = [c.id for c in db.query(models.Conversation).filter(
        models.Conversation.user_id == user_id).all()]
    if conv_ids:
        db.query(models.Message).filter(
            models.Message.conversation_id.in_(conv_ids)
        ).delete(synchronize_session=False)
    # 2) 删对话
    db.query(models.Conversation).filter(
        models.Conversation.user_id == user_id).delete(synchronize_session=False)
    # 3) 删该用户的需求（含历史已提交的）
    db.query(models.Requirement).filter(
        models.Requirement.user_id == user_id).delete(synchronize_session=False)
    # 4) 最后删用户
    db.delete(user)
    db.commit()
    return {"deleted": user_id}
