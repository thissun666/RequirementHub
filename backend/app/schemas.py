from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from .models import UserRole, RequirementStatus

# User schemas
class UserBase(BaseModel):
    username: str
    department: Optional[str] = None
    position: Optional[str] = None  # 新增

class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.USER

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None  # 新增

class UserOut(UserBase):
    id: int
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True

# Position schemas
class PositionOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None

# Conversation schemas
class ConversationBase(BaseModel):
    id: str

class ConversationCreate(BaseModel):
    pass

class ConversationOut(BaseModel):
    id: str
    user_id: int
    requirement_id: Optional[int]
    title: Optional[str] = None
    mode: str = "requirement"
    created_at: datetime
    updated_at: datetime
    class Config: from_attributes = True


# Message schemas
class MessageCreate(BaseModel):
    content: str
    sender_type: str

class MessageOut(BaseModel):
    id: int
    conversation_id: str
    sender_type: str
    content: str
    attachment_name: Optional[str] = None
    attachment_path: Optional[str] = None
    created_at: datetime
    is_private: bool = False


    class Config:
        from_attributes = True

# Requirement schemas
class RequirementBase(BaseModel):
    title: str
    description: str
    priority: str = "中"

class RequirementCreate(RequirementBase):
    conversation_id: str
    user_id: int

class RequirementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[RequirementStatus] = None
    solution: Optional[str] = None

class RequirementOut(BaseModel):
    id: int
    conversation_id: str
    user_id: int
    title: str
    description: str
    priority: str
    status: RequirementStatus
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    solution: Optional[str]

    class Config:
        from_attributes = True

class RequirementDetail(RequirementOut):
    messages: List[MessageOut] = []

# Request models
class MessageSend(BaseModel):
    content: str

class ReplyRequest(BaseModel):
    content: str

class ResolveRequest(BaseModel):
    result: str
    solution: str
    remark: Optional[str] = None