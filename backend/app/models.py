from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import enum

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"

class RequirementStatus(str, enum.Enum):
    PENDING = "待处理"
    PROCESSING = "处理中"
    WAITING_FEEDBACK = "待反馈"
    RESOLVED = "已解决"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER)
    department = Column(String(100), nullable=True)
    position = Column(String(100), nullable=True)  # 新增：职位
    preferred_model = Column(String(100), nullable=True)  # 子节点个人模型偏好（第二批接通UI）

    created_at = Column(DateTime, default=datetime.utcnow)

    requirements = relationship("Requirement", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")

class Requirement(Base):
    __tablename__ = "requirements"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(10), default="中")
    status = Column(Enum(RequirementStatus), default=RequirementStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    solution = Column(Text, nullable=True)

    user = relationship("User", back_populates="requirements")
    conversation = relationship("Conversation", back_populates="requirement", uselist=False)

class Conversation(Base):
    __tablename__ = "conversations"
    is_hidden = Column(Boolean, default=False)   # 软删除标记：隐藏后数据仍保留

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=True)
    mode = Column(String(20), default="requirement")   # requirement=需求模式 / chat=助手模式
    title = Column(String(100), nullable=True)          # 对话标题（支持改名）

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    requirement = relationship("Requirement", back_populates="conversation")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id"), nullable=False)
    sender_type = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    attachment_name = Column(String(255), nullable=True)  # 附件原始文件名（第二批接通上传）
    attachment_path = Column(String(500), nullable=True)  # 附件存储路径
    is_private = Column(Boolean, default=False)   # 助手模式消息对管理员隐藏

    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(32), index=True, nullable=False)
    title = Column(String(200), nullable=False)
    source_name = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=False)   # JSON数组形式的向量
    created_at = Column(DateTime, default=datetime.utcnow)
class UserAIConfig(Base):
    """子节点个人专属AI配置：仅对该用户生效，不影响系统配置"""
    __tablename__ = "user_ai_configs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    provider = Column(String(50), default="zhipu")        # zhipu / siliconflow / ollama
    api_key = Column(String(500), default="")
    model = Column(String(100), default="")
    base_url = Column(String(255), default="")
    updated_at = Column(DateTime, default=datetime.utcnow)
