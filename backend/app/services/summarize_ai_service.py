from typing import Dict, Any, List
import json
from .llm_service import llm_service

class SummarizeAIService:
    def __init__(self):
        self.prompt_template = """
你是一个需求整理专家，请根据以下对话历史，提取关键信息，生成一份结构化的需求描述。
对话历史：
{history}

请输出一个 JSON 对象，包含以下字段：
- "title": 简短标题（不超过15个字）
- "description": 详细描述（完整、有条理，涵盖目标、时间、资源等）
- "suggested_priority": 建议优先级，值为 "高"、"中"、"低" 之一（根据需求紧迫性、复杂度、涉及方等判断）

只输出 JSON，不要有其他文字。
"""
    def _ensure_str(self, val, max_len=5000):
        """AI可能返回嵌套dict/list，转成可读文本，避免SQLite绑定失败"""
        if val is None:
            return ""
        if isinstance(val, str):
            return val[:max_len]
        if isinstance(val, (dict, list)):
            try:
                lines = []
                if isinstance(val, dict):
                    for k, v in val.items():
                        lines.append(f"{k}：{v}")
                else:
                    for i, v in enumerate(val, 1):
                        lines.append(f"{i}. {v}")
                return "\n".join(lines)[:max_len]
            except Exception:
                return json.dumps(val, ensure_ascii=False)[:max_len]
        return str(val)[:max_len]

    def summarize(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """从对话中提取结构化需求"""
        messages = [
            {"role": "system", "content": "你是一个需求整理专家，只输出JSON。"},
            {"role": "user", "content": self.prompt_template.format(
                history=self._format_history(history)
            )}
        ]
        response = llm_service.chat_completion(messages, temperature=0.3)
        if not response:
            # 降级：返回默认结构
            return {
                "title": "未命名需求",
                "description": "AI未能生成完整描述，请手动补充。",
                "suggested_priority": "中"
            }
        try:
            # 尝试解析JSON
            # 有些模型可能会包含markdown代码块，清理
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
                data = json.loads(cleaned)
                return {
                    "title": self._ensure_str(data.get("title", "未命名需求"), 100),
                    "description": self._ensure_str(data.get("description", ""), 5000),
                    "suggested_priority": data.get("suggested_priority", "中")
                }

        except json.JSONDecodeError:
            # 解析失败，使用原始文本
            return {
                "title": "需求摘要",
                "description": response[:500],
                "suggested_priority": "中"
            }

    def _format_history(self, history: List[Dict[str, str]]) -> str:
        lines = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

summarize_ai_service = SummarizeAIService()