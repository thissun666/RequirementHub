import re
import uuid
import httpx
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, auth
from ..services import knowledge_service
from ..config import KNOWLEDGE_DIR

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _safe_filename(name: str) -> str:
    name = Path(name or "file").name
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip()
    return (name[:80] or "file")


def _read_text(path: Path) -> str:
    suffix = path.suffix.lower()
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
    return ""


def _friendly_ingest(e: Exception):
    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
        raise HTTPException(status_code=429, detail="向量服务限流，请1-2分钟后再试")
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))
    raise HTTPException(status_code=500, detail=f"入库失败: {e}")


@router.get("/")
def list_docs(db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin_user)):
    rows = db.query(models.KnowledgeItem).all()
    docs = {}
    for r in rows:
        d = docs.setdefault(r.doc_id, {
            "doc_id": r.doc_id, "title": r.title, "source_name": r.source_name,
            "chunks": 0, "created_at": str(r.created_at)})
        d["chunks"] += 1
    return list(docs.values())


@router.post("/text")
def add_text_doc(data: dict, db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin_user)):
    title = (data.get("title") or "").strip() or "未命名文档"
    content = (data.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")
    try:
        return knowledge_service.add_document(db, title, content)
    except Exception as e:
        _friendly_ingest(e)


@router.post("/upload")
def upload_doc(file: UploadFile = File(...), db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin_user)):
    safe_name = _safe_filename(file.filename or "")
    suffix = Path(safe_name).suffix.lower()
    if suffix not in (".txt", ".md", ".docx"):
        raise HTTPException(status_code=400, detail="仅支持 txt / md / docx")
    raw = file.file.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件不能超过20MB")
    tmp = KNOWLEDGE_DIR / f"{uuid.uuid4().hex}_{safe_name}"
    tmp.write_bytes(raw)
    try:
        text = _read_text(tmp)
    finally:
        tmp.unlink(missing_ok=True)
    if not text.strip():
        raise HTTPException(status_code=400, detail="无法从文件提取文本")
    try:
        return knowledge_service.add_document(db, Path(safe_name).stem, text, source_name=safe_name)
    except Exception as e:
        _friendly_ingest(e)


@router.delete("/doc/{doc_id}")
def delete_doc(doc_id: str, db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin_user)):
    n = db.query(models.KnowledgeItem).filter(models.KnowledgeItem.doc_id == doc_id).delete()
    db.commit()
    if not n:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"deleted": n}


@router.get("/search")
def search_kb(q: str, db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin_user)):
    return knowledge_service.search(db, q, top_k=5)


@router.post("/ask")
def ask_kb(data: dict, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    question = (data.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    return {"answer": knowledge_service.assistant_ask(db, question)}
