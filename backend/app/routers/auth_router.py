from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from ..database import get_db
from .. import models, schemas, auth

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = auth.create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=schemas.UserOut)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin_user)):
    existing = db.query(models.User).filter(models.User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed = auth.get_password_hash(user_data.password)
    new_user = models.User(
        username=user_data.username,
        password_hash=hashed,
        role=user_data.role,
        department=user_data.department,
        is_leader=user_data.is_leader
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
@router.get("/me")
def read_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role.value,
        "department": current_user.department,
        "position": current_user.position,
        "preferred_model": current_user.preferred_model,
    }
@router.put("/me/model")
def set_my_model(data: dict, db: Session = Depends(get_db),
                 current_user: models.User = Depends(auth.get_current_active_user)):
    """子节点设置个人偏好模型（只影响自己）"""
    model = (data.get("model") or "").strip()
    current_user.preferred_model = model or None
    db.commit()
    return {"preferred_model": current_user.preferred_model}

