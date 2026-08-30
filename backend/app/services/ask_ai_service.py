from typing import List, Dict, Optional
from .llm_service import llm_service
import logging

logger = logging.getLogger(__name__)


class AskAIService:
    MAX_ROUNDS = 3  # 最多追问3轮

    # ★ 系统提示词重写：优先问细节、不主动问时间、明令禁止重复提问
    SYSTEM_PROMPT = """你是一个需求收集助手，正在与部门员工对话，目标是用最少的轮次收集一条清晰的需求。

提问优先级（严格遵守）：
1. 优先澄清需求的具体内容、目标、使用场景、要解决的具体问题
2. 其次是涉及的部门、人员或系统资源
3. 最后是特殊要求或注意事项

关于完成时间：
- 不要主动追问完成时间或期限！用户如果着急会自己说。
- 仅当用户主动提到时间且表述模糊时（如"尽快"），才确认一次具体节点。

提问规则：
- 每轮只问1个问题，简短，尽量给选择题
- 禁止重复提问：提问前必须检查对话历史，凡已问过或语义相同的问题一律不得再问
- 当需求目标、场景、资源已基本清楚时，只输出六个字符：[DONE]

以下是对话历史。请输出你的下一条回复：若信息已足够只输出[DONE]，否则只输出一个不重复的追问。"""


    def generate_question(self, history: List[Dict[str, str]], round_num: int) -> Optional[str]:
        """根据对话历史生成下一个追问；判断信息足够则返回 None。"""
        if round_num >= self.MAX_ROUNDS:
            return None

        # ★ 关键修复：把历史作为真正的多轮消息传入，模型能看清每轮谁说了什么，
        #   从根源上解决"重复问同一个问题"
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            *history,   # [{"role":"user"/"assistant","content":...}, ...] 交替排列
        ]

        try:
            response = llm_service.chat_completion(messages, temperature=0.5)
        except Exception as e:
            logger.error(f"❌ 询问AI调用失败: {e}")
            return "⚠️ AI服务暂时不可用，您的消息已保存，请稍后重试。"

        if not response:
            return None

        resp = response.strip()
        if "[DONE]" in resp or "信息已足够" in resp:
            return None

        # ★ 兜底防重复：与历史中AI已问过的问题完全相同 → 视为无效，转入需求生成
        ai_asked = [m["content"].strip() for m in history if m["role"] == "assistant"]
        if resp in ai_asked:
            logger.warning(f"⚠️ AI重复提问被拦截: {resp[:30]}...")
            return None

        # 兜底：过短且不含问号的回复视为结束语
        if len(resp) <= 18 and "?" not in resp and "？" not in resp:
            return None
        return resp


ask_ai_service = AskAIService()
