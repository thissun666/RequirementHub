from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from .. import models, schemas, auth

router = APIRouter(prefix="/api/requirements", tags=["requirements"])

@router.get("/")
def list_requirements(
    status: Optional[models.RequirementStatus] = Query(None),
    priority: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    query = db.query(models.Requirement)
    if current_user.role == models.UserRole.USER:
        query = query.filter(models.Requirement.user_id == current_user.id)
    elif user_id is not None:
        query = query.filter(models.Requirement.user_id == user_id)
    if status:
        query = query.filter(models.Requirement.status == status)
    if priority:
        query = query.filter(models.Requirement.priority == priority)
    reqs = query.order_by(models.Requirement.updated_at.desc()).all()

    user_ids = {r.user_id for r in reqs}
    users = {u.id: u for u in db.query(models.User).filter(
        models.User.id.in_(user_ids)).all()} if user_ids else {}

    out = []
    for r in reqs:
        u = users.get(r.user_id)
        out.append({
            "id": r.id, "title": r.title, "description": r.description,
            "priority": r.priority,
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "user_id": r.user_id,
            "username": u.username if u else f"用户{r.user_id}",
            "department": (u.department if u and u.department else "未填部门"),
            "created_at": str(r.created_at), "updated_at": str(r.updated_at),
        })
    return out

@router.get("/{requirement_id}", response_model=schemas.RequirementDetail)
def get_requirement_detail(
    requirement_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """获取需求详情，包含所有消息"""
    req = db.query(models.Requirement).filter(models.Requirement.id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    # 权限检查：子节点只能看自己的，父节点可看所有
    if req.user_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # 获取关联对话的所有消息
    conv = db.query(models.Conversation).filter(models.Conversation.id == req.conversation_id).first()
    messages = []
    if conv:
        messages = db.query(models.Message).filter(
            models.Message.conversation_id == conv.id
        ).order_by(models.Message.created_at.asc()).all()
    
    # 构造详情
    detail = schemas.RequirementDetail.from_orm(req)
    detail.messages = [schemas.MessageOut.from_orm(m) for m in messages]
    return detail

@router.post("/{requirement_id}/reply", response_model=schemas.MessageOut)
def reply_to_requirement(
    requirement_id: int,
    reply_data: schemas.ReplyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """父节点回复需求（向子节点发送消息）"""
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can reply")
    
    req = db.query(models.Requirement).filter(models.Requirement.id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    
    # 更新状态为处理中（如果当前是待处理）
    if req.status == models.RequirementStatus.PENDING:
        req.status = models.RequirementStatus.PROCESSING
    
    # 在关联对话中添加一条admin消息
    conv = db.query(models.Conversation).filter(models.Conversation.id == req.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    new_msg = models.Message(
        conversation_id=conv.id,
        sender_type="admin",
        content=reply_data.content,
        created_at=datetime.utcnow()
    )
    db.add(new_msg)
    conv.updated_at = datetime.utcnow()
    req.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(new_msg)
    return new_msg

@router.post("/{requirement_id}/resolve", response_model=schemas.RequirementOut)
def resolve_requirement(
    requirement_id: int,
    resolve_data: schemas.ResolveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin_user)
):
    """父节点标记需求解决，推送解决方案给子节点"""
    req = db.query(models.Requirement).filter(models.Requirement.id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    
    # 更新需求信息
    req.status = models.RequirementStatus.RESOLVED

    req.solution = f"处理结果: {resolve_data.result}\n解决方案: {resolve_data.solution}"
    if resolve_data.remark:
        req.solution += f"\n备注: {resolve_data.remark}"
    req.resolved_at = datetime.utcnow()
    req.updated_at = datetime.utcnow()
    
    # 在对话中添加一条admin消息，通知子节点
    conv = db.query(models.Conversation).filter(models.Conversation.id == req.conversation_id).first()
    if conv:
        msg_content = f"【父节点已反馈】\n结果: {resolve_data.result}\n方案: {resolve_data.solution}"
        if resolve_data.remark:
            msg_content += f"\n备注: {resolve_data.remark}"
        new_msg = models.Message(
            conversation_id=conv.id,
            sender_type="admin",
            content=msg_content,
            created_at=datetime.utcnow()
        )
        db.add(new_msg)
        conv.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(req)
    return req

@router.put("/{requirement_id}/status", response_model=schemas.RequirementOut)
def update_status(
    requirement_id: int,
    new_status: models.RequirementStatus,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    更新需求状态（子节点确认解决或重新打开）
    仅允许子节点更新自己的需求，或父节点更新任意
    """
    req = db.query(models.Requirement).filter(models.Requirement.id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    
    # 权限：子节点只能改自己的
    if current_user.role == models.UserRole.USER and req.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # 状态流转规则（简单版）
    if current_user.role == models.UserRole.USER:
        # 子节点只能将待反馈改为已解决，或将已解决改为处理中（重新打开）
        if req.status == models.RequirementStatus.WAITING_FEEDBACK and new_status == models.RequirementStatus.RESOLVED:
            req.status = new_status
        elif req.status == models.RequirementStatus.RESOLVED and new_status == models.RequirementStatus.PROCESSING:
            req.status = new_status
            # 自动添加一条消息表示重新打开
            conv = db.query(models.Conversation).filter(models.Conversation.id == req.conversation_id).first()
            if conv:
                reopen_msg = models.Message(
                    conversation_id=conv.id,
                    sender_type="user",
                    content="【子节点重新打开】该需求需要继续处理。",
                    created_at=datetime.utcnow()
                )
                db.add(reopen_msg)
                conv.updated_at = datetime.utcnow()
        else:
            raise HTTPException(status_code=400, detail="Invalid status transition")
    else:
        # 父节点可以任意改（但一般不直接改）
        req.status = new_status
    
    req.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(req)
    return req