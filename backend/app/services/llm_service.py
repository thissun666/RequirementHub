import httpx
import json
import logging
from typing import Optional, Dict, Any, List
from ..config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.api_key = settings.AI_API_KEY
        self.model = settings.AI_MODEL
        self.base_url = settings.AI_BASE_URL.rstrip('/')
        self.client = httpx.Client(timeout=60.0)
        
        # 打印配置状态
        logger.info(f"🤖 LLM配置: provider={self.provider}, model={self.model}, base_url={self.base_url}")
        if self.api_key:
            logger.info(f"✅ API Key 已配置 (长度: {len(self.api_key)} 字符)")
        else:
            logger.error("❌ API Key 为空！请检查 .env 文件中的 AI_API_KEY")
    def configure(self, provider=None, api_key=None, model=None, base_url=None):
        """模型设置页保存后热更新本实例，无需重启"""
        if provider:
            self.provider = provider
        if api_key:
            if api_key != self.api_key:
                logger.info(f"🔑 LLM 配置热更新: provider={provider}, model={model}, key={api_key[:4]}****")
            self.api_key = api_key
        if model:
            self.model = model
        if base_url:
            self.base_url = base_url.rstrip('/')

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.provider == "ollama":
            return headers
        # 所有其他提供商都需要 Bearer Token
        if not self.api_key:
            logger.error("❌ API Key 为空，无法构建 Authorization 头")
            return headers
        headers["Authorization"] = f"Bearer {self.api_key}"
        logger.debug(f"🔑 Authorization: Bearer {self.api_key[:4]}...{self.api_key[-4:]}")
        return headers

    def _get_api_url(self) -> str:
        if self.provider == "ollama":
            return f"{self.base_url}/api/chat"
        else:
            # 智谱/硅基/OpenAI兼容
            return f"{self.base_url}/chat/completions"
    def _build_payload(self, messages, temperature=0.7, model=None):
        """按服务商组装请求体（model参数支持按用户偏好覆盖）"""
        if self.provider == "ollama":
            return {
                "model": model or self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            }
        # 智谱 / 硅基流动 / 其它 OpenAI 兼容接口
        return {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
        }


    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7, model: str = None) -> str:
        try:
            headers = self._build_headers()
            if not self.api_key and self.provider != "ollama":
                logger.error("❌ API Key 为空，拒绝调用。请到父节点【模型设置】填写并保存，或检查 backend/.env")
                raise RuntimeError("AI_API_KEY 未配置，无法调用大模型")
            
            payload = self._build_payload(messages, temperature, model)
            url = self._get_api_url()
            
            logger.info(f"📤 发送LLM请求: {url}")
            logger.debug(f"📦 Payload: {json.dumps(payload, ensure_ascii=False)[:200]}...")
            
            response = self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if "choices" in data:
                content = data["choices"][0]["message"]["content"].strip()
                logger.info(f"✅ LLM响应成功，长度: {len(content)} 字符")
                return content
            elif "response" in data:
                content = data["response"].strip()
                logger.info(f"✅ Ollama响应成功，长度: {len(content)} 字符")
                return content
            else:
                logger.warning(f"⚠️ 未知响应格式: {list(data.keys())}")
                return ""
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP状态错误: {e.response.status_code}, {e.response.text[:200]}")
            return ""
        except Exception as e:
            logger.error(f"❌ LLM调用失败: {e}")
            return ""

    # ... 其他方法保持不变

    def chat_completion_async(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """
        异步版本（供WebSocket使用），此处为了简化同步实现，实际可以包装。
        本项目初期使用同步，后续可改造。
        """
        return self.chat_completion(messages, temperature)
    def embedding(self, texts):
        """向量化：自动分批 + 429限流指数退避重试（整体替换原方法）"""
        import time as _time
        import httpx
        if isinstance(texts, str):
            texts = [texts]
        all_vectors = []
        BATCH = 5            # 每批条数：小批慢发，避开限流窗口
        MAX_RETRIES = 6      # 单批最多重试6次（2+4+8+16+32+60≈2分钟）
        url = "https://open.bigmodel.cn/api/paas/v4/embeddings"
        headers = {"Authorization": f"Bearer {self.api_key}"}   # ★ 若key变量名不同改这里
        for i in range(0, len(texts), BATCH):
            batch = texts[i:i + BATCH]
            delay = 2
            for attempt in range(MAX_RETRIES):
                try:
                    resp = httpx.post(url, headers=headers,
                                      json={"model": "embedding-2", "input": batch},
                                      timeout=60)
                    resp.raise_for_status()
                    data = resp.json()
                    embs = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                    all_vectors.extend(e["embedding"] for e in embs)
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                        logger.warning(f"向量化限流(429)，{delay}s后重试 "
                                       f"({attempt + 1}/{MAX_RETRIES})，批 {i}-{i+len(batch)}")
                        _time.sleep(delay)
                        delay = min(delay * 2, 60)
                    else:
                        raise
                except Exception:
                    if attempt < MAX_RETRIES - 1:
                        _time.sleep(delay)
                        delay = min(delay * 2, 60)
                    else:
                        raise
            if i + BATCH < len(texts):
                _time.sleep(1)   # 批间停顿，进一步降低触发限流的概率
        return all_vectors

# 单例
llm_service = LLMService()