# ===== 用户个人专属LLM调用器（OpenAI兼容协议：主流服务商+本地+自定义均适用）=====
import logging
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)

DEFAULT_BASES = {
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
    "custom": "",   # 自定义：必须由用户填写 base_url
}


class UserLLMService:
    def chat_completion(self, messages, provider, api_key, model, base_url, temperature=0.6):
        if OpenAI is None:
            logger.error("服务器未安装 openai 库，请执行: pip install openai")
            return None
        if not model:
            return None
        base = (base_url or "").strip().rstrip("/") or DEFAULT_BASES.get(provider, "")
        if not base:
            logger.error(f"提供商 {provider} 缺少 Base URL")
            return None
        key = (api_key or "").strip() or ("ollama" if provider == "ollama" else "empty")
        try:
            client = OpenAI(api_key=key, base_url=base)
            resp = client.chat.completions.create(
                model=model, messages=messages, temperature=temperature)
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"个人模型调用失败({provider}/{model}): {e}")
            return None


user_llm_service = UserLLMService()
