import re
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..config import UPLOAD_DIR
from .. import models, schemas, auth
from ..services.ask_ai_service import ask_ai_service
from ..services.summarize_ai_service import summarize_ai_service
from ..services.priority_service import priority_service
from ..services.websocket_manager import websocket_manager
from ..services.llm_service import llm_service
from ..services.user_llm_service import user_llm_service
from ..services import knowledge_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _safe_filename(name: str) -> str:
    """清洗文件名：剥路径 + 替换Windows非法字符/控制符 + 限长"""
    name = Path(name or "file").name
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip()
    return (name[:80] or "file")


@router.post("/", response_model=schemas.ConversationOut)
def create_conversation(
    mode: str = "requirement",
    title: str = "未命名需求",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if mode not in ("requirement", "chat"):
        mode = "requirement"
    new_conv = models.Conversation(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        mode=mode,
        title=(title or "未命名需求")[:100],
    )
    db.add(new_conv)
    db.commit()
    db.refresh(new_conv)
    return new_conv


@router.put("/{conversation_id}/title")
def rename_conversation(
    conversation_id: str,
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")
    new_title = (data.get("title") or "").strip()[:100]
    if not new_title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    conv.title = new_title
    conv.updated_at = datetime.utcnow()
    db.commit()
    return {"id": conv.id, "title": conv.title}


@router.put("/{conversation_id}/mode")
def switch_conversation_mode(
    conversation_id: str,
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")
    mode = (data.get("mode") or "").strip()
    if mode not in ("requirement", "chat"):
        raise HTTPException(status_code=400, detail="无效的模式")
    if conv.requirement_id is not None:
        raise HTTPException(status_code=400, detail="该需求已提交，处于跟进阶段，不能切回需求收集模式")
    conv.mode = mode
    conv.updated_at = datetime.utcnow()
    db.commit()
    return {"id": conv.id, "mode": conv.mode}


@router.get("/", response_model=List[schemas.ConversationOut])
def list_conversations(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    convs = db.query(models.Conversation).filter(
        models.Conversation.user_id == current_user.id,
        models.Conversation.is_hidden == False,   # ★ 隐藏的对话不出现在列表
    ).order_by(models.Conversation.updated_at.desc()).all()
    return convs


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """★ 软删除：仅隐藏对话，消息数据保留在数据库中。
       已提交需求的对话不允许隐藏（需求历史必须保留给管理员）。"""
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")
    if conv.requirement_id is not None:
        raise HTTPException(status_code=400, detail="该对话已关联需求，不支持隐藏")
    conv.is_hidden = True
    conv.updated_at = datetime.utcnow()
    db.commit()
    return {"hidden": conv.id}


@router.get("/{conversation_id}/messages", response_model=List[schemas.MessageOut])
def get_messages(conversation_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    conv = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")
    messages = db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id
    ).order_by(models.Message.created_at.asc()).all()
    return messages


def _extract_attachment_text(stored_name: str) -> str:
    """从上传的txt/md/docx中提取纯文本，注入AI上下文"""
    path = UPLOAD_DIR / stored_name
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    try:
        if suffix in (".txt", ".md"):
            for enc in ("utf-8", "gbk"):
                try:
                    return path.read_text(encoding=enc)
                except UnicodeDecodeError:
                    continue
            return ""
        if suffix == ".docx":
            from docx import Document
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        logger.warning(f"附件文本提取失败 {stored_name}: {e}")
    return ""


# 正在执行AI处理的对话集合（防止同一对话被并发触发两次AI逻辑）
_ai_processing = set()


def _call_llm_for_user(db, user, messages, temperature):
    """★ 个人专属模型优先；未配置或调用失败回退系统模型"""
    if user:
        cfg = db.query(models.UserAIConfig).filter(
            models.UserAIConfig.user_id == user.id).first()
        if cfg and cfg.model and cfg.provider:
            reply = user_llm_service.chat_completion(
                messages, provider=cfg.provider, api_key=cfg.api_key,
                model=cfg.model, base_url=cfg.base_url, temperature=temperature)
            if reply:
                return reply
            logger.warning("个人模型调用失败，回退系统模型")
    return llm_service.chat_completion(
        messages, temperature=temperature,
        model=(user.preferred_model if user and user.preferred_model else None))


def _user_requirements_context(db, user_id: int) -> str:
    """子节点助手只能看到【自己的】需求数据（隐私边界）"""
    try:
        reqs = db.query(models.Requirement).filter(
            models.Requirement.user_id == user_id
        ).order_by(models.Requirement.updated_at.desc()).all()
    except Exception as e:
        logger.warning(f"读取用户需求数据失败: {e}")
        return "（数据暂时不可用）"
    if not reqs:
        return "（该员工还没有提交过需求）"
    lines = [f"共提交{len(reqs)}个需求："]
    for r in reqs[:8]:
        st = getattr(r.status, "value", None) or str(r.status)
        lines.append(f"- [{r.priority}][{st}] {r.title}")
    return "\n".join(lines)


def _process_ai_logic(conversation_id: str):
    if conversation_id in _ai_processing:
        logger.info(f"⏭️ 对话 {conversation_id} 正在处理中，跳过本次触发")
        return
    _ai_processing.add(conversation_id)
    db = SessionLocal()
    try:
        conv = db.query(models.Conversation).filter(
            models.Conversation.id == conversation_id).first()
        if not conv:
            return
        conv_mode = getattr(conv, "mode", None) or "requirement"

        all_msgs = db.query(models.Message).filter(
            models.Message.conversation_id == conversation_id
        ).order_by(models.Message.created_at.asc()).all()

        # 隐私上下文分离：history_all=全量(助手模式自用)；history_visible=剔除私密(其余用)
        history_all, history_visible = [], []
        for m in all_msgs:
            if m.sender_type not in ("user", "ai"):
                continue
            content = m.content
            if m.attachment_path:
                extra = _extract_attachment_text(m.attachment_path)
                if extra:
                    content += f"\n\n[用户上传附件 {m.attachment_name} 的内容]\n{extra[:4000]}"
            entry = {"role": "user" if m.sender_type == "user" else "assistant",
                     "content": content}
            history_all.append(entry)
            if not getattr(m, "is_private", False):
                history_visible.append(entry)

        last_user = next((m for m in reversed(all_msgs)
                          if m.sender_type == "user" and not getattr(m, "is_private", False)), None)
        user = db.query(models.User).filter(models.User.id == conv.user_id).first()
        uname = user.username if user else f"用户{conv.user_id}"

        # ===== 模式A：助手聊天（知识库+本人需求感知；回复标记私密）=====
        if conv_mode == "chat":
            last_q = next((m for m in reversed(all_msgs) if m.sender_type == "user"), None)
            kb_part, sys_ctx = "（知识库未检索到相关内容）", "（暂无数据）"
            if last_q:
                try:
                    hits = knowledge_service.search(db, last_q.content, top_k=3)
                    if hits:
                        kb_part = "\n\n".join(f"[{h['title']}] {h['content']}" for h in hits)
                except Exception as e:
                    logger.warning(f"助手知识库检索失败: {e}")
            sys_ctx = _user_requirements_context(db, conv.user_id)
            sys_prompt = (
                "你是企业员工的智能助手。回答时综合三类信息：\n"
                "1)【该员工的需求数据】：问'我的需求/申请进度'等时依据此回答；\n"
                "2)【知识库资料】：公司制度/流程问题依据资料回答并注明来源，未提及的明确说明；\n"
                "3) 都无关时：通用助手简洁回答，禁止编造数据。\n"
                "中文回答，简洁清晰。\n\n"
                f"【该员工的需求数据】\n{sys_ctx}\n\n【知识库资料】\n{kb_part[:4000]}"
            )
            reply = _call_llm_for_user(db, user,
                                       [{"role": "system", "content": sys_prompt}, *history_all], 0.6)
            if reply:
                db.add(models.Message(conversation_id=conversation_id, sender_type="ai",
                                      content=reply, is_private=True, created_at=datetime.utcnow()))
                conv.updated_at = datetime.utcnow()
                db.commit()
            return

        # ===== 模式B：跟进（已提交需求，管理员可见）=====
        if conv.requirement_id is not None:
            req = db.query(models.Requirement).filter(
                models.Requirement.id == conv.requirement_id).first()
            websocket_manager.notify_admins_threadsafe({
                "type": "new_message",
                "requirement_id": conv.requirement_id,
                "title": req.title if req else "需求",
                "username": uname,
                "content": last_user.content if last_user else "",
                "timestamp": str(datetime.utcnow())
            })
            reply = _call_llm_for_user(db, user,
                                       [{"role": "system", "content": "你是需求跟进助手。该需求已提交给管理员处理。请确认已同步管理员，并就用户补充内容简短回应，两三句以内，不要重新发起需求收集。"},
                                        *history_visible], 0.5)
            if reply:
                db.add(models.Message(conversation_id=conversation_id, sender_type="ai",
                                      content=reply, created_at=datetime.utcnow()))
                conv.updated_at = datetime.utcnow()
                db.commit()
                logger.info("💬 [跟进] 已推送管理员并回复子节点")
            return

        # ===== 模式C：需求收集 =====
        round_num = len([m for m in all_msgs if m.sender_type == "ai"])
        logger.info(f"🤖 [后台] AI逻辑启动: 可见历史{len(history_visible)}条, 轮次{round_num}")

        need_summary = round_num >= ask_ai_service.MAX_ROUNDS
        if not need_summary:
            question = ask_ai_service.generate_question(history_visible, round_num)
            if question:
                db.add(models.Message(conversation_id=conversation_id, sender_type="ai",
                                      content=question, created_at=datetime.utcnow()))
                conv.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"💬 [后台] AI追问已生成: {question[:50]}...")
            return

        logger.info("ℹ️ [后台] AI判断无需追问，转入需求生成")
        summary = summarize_ai_service.summarize(history_visible)
        logger.info(f"📝 AI生成摘要: {summary}")

        # ★★★ 标题修复：AI摘要标题缺失/为默认值时，回退用员工自己起的会话名 ★★★
        def _bad_title(t):
            t = (t or "").strip()
            return (not t) or t in ("未命名需求", "未命名", "新需求")

        ai_title, final_desc, final_pri = "", "", "中"
        if isinstance(summary, dict):
            ai_title = (summary.get("title") or "").strip()
            final_desc = (summary.get("description") or "").strip()
            final_pri = summary.get("suggested_priority") or "中"
        conv_title = (conv.title or "").strip()
        if _bad_title(ai_title) and not _bad_title(conv_title):
            ai_title = conv_title  # 用会话标题兜底
        final_title = (ai_title or "未命名需求")[:100]
        if not final_desc:
            final_desc = "\n".join(m.get("content", "") for m in history_visible[:6])[:2000]
        if final_pri not in ("高", "中", "低"):
            final_pri = "中"
        if _bad_title(conv.title):
            conv.title = final_title  # 侧边栏同步显示有意义的标题

        new_req = models.Requirement(
            conversation_id=conversation_id,
            user_id=conv.user_id,
            title=final_title,
            description=final_desc,
            priority=final_pri,
            status=models.RequirementStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_req)
        db.flush()

        final_priority = final_pri
        try:
            rule_score = priority_service.calculate_priority(new_req, user, db)
            final_priority = priority_service.final_priority(rule_score, final_pri)
            new_req.priority = final_priority
        except Exception as e:
            logger.warning(f"优先级计算失败，使用AI建议值: {e}")

        db.add(models.Message(
            conversation_id=conversation_id, sender_type="ai",
            content=f"✅ 您的需求「{final_title}」已整理并提交给管理员，请耐心等待处理。",
            created_at=datetime.utcnow()
        ))
        conv.requirement_id = new_req.id
        conv.updated_at = datetime.utcnow()
        db.commit()

        websocket_manager.notify_admins_threadsafe({
            "type": "new_requirement",
            "requirement_id": new_req.id,
            "title": final_title,
            "user_id": conv.user_id,
            "username": uname,
            "timestamp": str(datetime.utcnow())
        })
        logger.info(f"✅ [后台] 需求已创建: ID={new_req.id}, 标题={final_title}, 优先级={final_priority}")

    except Exception as e:
        logger.error(f"❌ [后台] AI处理失败: {e}")
        db.rollback()
    finally:
        db.close()
        _ai_processing.discard(conversation_id)   # ★ 必须在finally内：任何return路径都会执行

@router.post("/{conversation_id}/messages", response_model=schemas.MessageOut)
def send_message(
    conversation_id: str,
    msg_data: schemas.MessageSend,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if not (msg_data.content or "").strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    if len(msg_data.content) > 5000:
        raise HTTPException(status_code=400, detail="单条消息不能超过5000字符，请分条发送")

    logger.info(f"📩 收到消息: conv={conversation_id}, 用户={current_user.id}, 内容={msg_data.content[:50]}...")
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")

    sender_type = "admin" if current_user.role == models.UserRole.ADMIN else "user"
    new_msg = models.Message(
        conversation_id=conversation_id,
        sender_type=sender_type,
        content=msg_data.content,
        is_private=(conv.mode == "chat"),   # ★ 助手模式的消息对管理员隐藏
        created_at=datetime.utcnow()
    )
    db.add(new_msg)
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(new_msg)
    logger.info(f"✅ 消息已存储: {new_msg.id}")

    if current_user.role == models.UserRole.USER:
        background_tasks.add_task(_process_ai_logic, conversation_id)
    return new_msg


@router.post("/{conversation_id}/upload", response_model=schemas.MessageOut)
def upload_message_file(
    conversation_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")

    safe_name = _safe_filename(file.filename or "")
    suffix = Path(safe_name).suffix.lower()
    if suffix not in (".txt", ".md", ".docx"):
        raise HTTPException(status_code=400, detail="仅支持 txt / md / docx 文件")

    data = file.file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件不能超过10MB")

    stored = f"{uuid.uuid4().hex}_{safe_name}"
    (UPLOAD_DIR / stored).write_bytes(data)

    new_msg = models.Message(
        conversation_id=conversation_id,
        sender_type="admin" if current_user.role == models.UserRole.ADMIN else "user",
        content=f"📎 {safe_name}",
        attachment_name=safe_name,
        attachment_path=stored,
        is_private=(conv.mode == "chat"),
        created_at=datetime.utcnow(),
    )
    db.add(new_msg)
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(new_msg)

    if current_user.role == models.UserRole.USER:
        background_tasks.add_task(_process_ai_logic, conversation_id)
    return new_msg
