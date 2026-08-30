# ===== 企业知识库 + 管理员智能助手（向量检索+关键词兜底 + 系统数据感知）=====
import re
import json
import time as _time
import logging
from datetime import datetime

from .. import models
from ..services.llm_service import llm_service

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 5


def _chunk_text(text: str):
    """按段落行拼片，超长行滑窗切，片间保留重叠"""
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    chunks, buf = [], ""
    for ln in lines:
        if len(buf) + len(ln) + 1 <= CHUNK_SIZE:
            buf = (buf + "\n" + ln).strip()
            continue
        if buf:
            chunks.append(buf)
        while len(ln) > CHUNK_SIZE:
            chunks.append(ln[:CHUNK_SIZE])
            ln = ln[CHUNK_SIZE - CHUNK_OVERLAP:]
        buf = ln
    if buf:
        chunks.append(buf)
    return chunks


def _cosine(a, b):
    try:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        return dot / (na * nb) if na and nb else 0.0
    except Exception:
        return 0.0


def _keyword_score(question: str, content: str) -> float:
    """中文2-gram命中率：向量不可用时的兜底检索"""
    q = re.sub(r'\s+', '', question or '')
    if not q:
        return 0.0
    if len(q) < 2:
        return 1.0 if q in (content or '') else 0.0
    grams = {q[i:i + 2] for i in range(len(q) - 1)}
    hit = sum(1 for g in grams if g in (content or ''))
    return hit / len(grams)


# ---------- 向量化 ----------
def _embed_batch(texts, max_retries=5, base_delay=2):
    import httpx
    url = "https://open.bigmodel.cn/api/paas/v4/embeddings"
    headers = {"Authorization": f"Bearer {llm_service.api_key}"}
    delay = base_delay
    for attempt in range(max_retries):
        try:
            resp = httpx.post(url, headers=headers,
                              json={"model": "embedding-2", "input": texts}, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            embs = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
            return [e["embedding"] for e in embs]
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"向量化限流/失败，{delay}s后重试({attempt + 1}/{max_retries}): {e}")
            _time.sleep(delay)
            delay = min(delay * 2, 45)


def _embed_query(q):
    """★ 问题向量化：轻量重试(最多2次≈3s)，失败立即返回None转关键词——杜绝提问卡2分钟"""
    try:
        return _embed_batch([q], max_retries=2, base_delay=1)[0]
    except Exception as e:
        logger.warning(f"问题向量化失败，转关键词检索: {e}")
        return None


# ---------- 入库（429永不导致上传失败：失败转关键词模式） ----------
def add_document(db, title: str, content: str, source_name: str = None):
    content = (content or "").strip()
    if not content:
        raise ValueError("文档内容为空")
    chunks = _chunk_text(content)
    if not chunks:
        raise ValueError("未能切分出有效内容")

    vectors, warning = None, None
    try:
        vectors = []
        for i in range(0, len(chunks), 4):
            batch = chunks[i:i + 4]
            vectors.extend(_embed_batch(batch, max_retries=5, base_delay=2))
            if i + 4 < len(chunks):
                _time.sleep(1.5)
        if len(vectors) != len(chunks):
            vectors = None
    except Exception as e:
        logger.warning(f"向量化整体失败，按关键词模式入库: {e}")
        vectors = None
    if vectors is None:
        warning = "向量服务繁忙，已按关键词模式入库（检索正常可用；之后可删除重传以获得语义检索）"

    doc_id = f"doc_{int(datetime.utcnow().timestamp() * 1000)}"
    now = datetime.utcnow()
    for idx, chunk in enumerate(chunks):
        db.add(models.KnowledgeItem(
            doc_id=doc_id,
            title=(title or "未命名文档")[:100],
            content=chunk,
            embedding=json.dumps(vectors[idx]) if vectors else "",
            source_name=(source_name or "手输文本")[:120],
            created_at=now,
        ))
    db.commit()
    logger.info(f"📚 知识入库: {title} → {len(chunks)}片, 向量={'是' if vectors else '否(关键词)'}")
    return {"title": title, "chunks": len(chunks), "doc_id": doc_id, "warning": warning}


# ---------- 检索（向量+关键词混合） ----------
def search(db, q: str, top_k: int = TOP_K):
    q = (q or "").strip()
    if not q:
        return []
    qv = _embed_query(q)
    scored = []
    for r in db.query(models.KnowledgeItem).all():
        kw = _keyword_score(q, r.content)
        cos = 0.0
        if qv and r.embedding:
            try:
                cos = _cosine(qv, json.loads(r.embedding))
            except Exception:
                cos = 0.0
        final = cos * 0.75 + kw * 0.6
        if final > 0.08:
            scored.append((final, r))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [{"title": r.title, "content": r.content, "source": r.source_name,
             "score": round(f, 4)} for f, r in scored[:top_k]]


# ---------- 系统实时数据（供助手感知需求状态） ----------
def _requirements_context(db) -> str:
    try:
        reqs = db.query(models.Requirement).order_by(
            models.Requirement.updated_at.desc()).all()
    except Exception as e:
        logger.warning(f"读取需求数据失败: {e}")
        return "（系统数据暂时不可用）"

    def st(r):
        return getattr(r.status, "value", None) or str(r.status)

    by = {}
    for r in reqs:
        by[st(r)] = by.get(st(r), 0) + 1
    stat = "、".join(f"{k}{v}个" for k, v in by.items()) or "无"
    pri_order = {"高": 0, "中": 1, "低": 2}
    pending = sorted([r for r in reqs if st(r) != "已解决"],
                     key=lambda r: pri_order.get(r.priority, 3))[:5]
    lines = [f"需求总数{len(reqs)}个（{stat}）", "当前待办Top5："]
    if pending:
        for i, r in enumerate(pending, 1):
            u = db.query(models.User).filter(models.User.id == r.user_id).first()
            lines.append(f"{i}. [{r.priority}][{st(r)}] {r.title} —— {u.username if u else '用户' + str(r.user_id)}")
    else:
        lines.append("（无待办，全部已解决 🎉）")
    return "\n".join(lines)


# ---------- 管理员智能助手：单次LLM调用同时感知系统数据+知识库 ----------
def assistant_ask(db, question: str):
    q = (question or "").strip()
    if not q:
        return "请输入问题。"
    hits = search(db, q, top_k=4)
    kb_part = ("\n\n".join(f"[{h['title']}|{h['source']}] {h['content']}" for h in hits)
               if hits else "（知识库未检索到相关内容）")
    sys_prompt = (
        "你是管理员的企业智能助手。回答时综合三类信息源：\n"
        "1)【系统实时数据】：需求统计与待办清单。凡问'需求/待办/处理情况/统计/谁提交'等，必须依据此数据回答，可做汇总分析；\n"
        "2)【知识库资料】：凡问公司制度/流程/FAQ，依据资料回答并注明来自知识库；资料未提及的明确说明；\n"
        "3) 两者都无关时：作为通用助手直接简洁回答，禁止编造系统里不存在的数据。\n"
        "中文回答，条理清晰，可用短列表。"
    )
    user_msg = (f"【系统实时数据】\n{_requirements_context(db)}\n\n"
                f"【知识库资料】\n{kb_part[:5000]}\n\n问题：{q}")
    ans = llm_service.chat_completion(
        [{"role": "system", "content": sys_prompt},
         {"role": "user", "content": user_msg}],
        temperature=0.4)
    return ans or "AI暂时没有返回内容，请稍后重试。"


def ask(db, question: str):
    """兼容旧接口"""
    return assistant_ask(db, question)
