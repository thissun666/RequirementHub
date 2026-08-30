from typing import Dict, Any
from ..models import User, Requirement
from sqlalchemy.orm import Session

class PriorityService:
    @staticmethod
    def calculate_priority(req: Requirement, user: User, db: Session) -> str:
        """
        综合计算优先级（规则 + AI辅助，这里主要实现规则部分，
        AI建议优先级由 summarize_ai_service 提供，在此进行融合）
        """
        score = 0
        # 规则1：提交人是否为领导（User模型没有该字段时安全降级为False）
        if getattr(user, "is_leader", False):
            score += 3

        
        # 规则2：对话轮次（消息数量）越多说明越复杂
        conv = db.query(models.Conversation).filter(models.Conversation.id == req.conversation_id).first()
        if conv:
            msg_count = db.query(models.Message).filter(models.Message.conversation_id == conv.id).count()
            if msg_count > 10:
                score += 2
            elif msg_count > 5:
                score += 1
        
        # 规则3：描述长度（简单指标）
        if len(req.description) > 200:
            score += 1
        
        # 规则4：是否有特定关键词（紧急、重要、立即等），暂不实现词库
        
        # 结合AI建议：AI建议优先级由summarize_ai_service提供，但这里我们传入suggested_priority
        # 在调用时会将AI建议作为参数传入
        # 此方法只基于规则计算原始分，最终由外部结合AI建议
        return score

    @staticmethod
    def final_priority(rule_score: int, ai_suggested: str) -> str:
        """
        综合规则分和AI建议，输出最终优先级
        """
        # 将AI建议映射为分数
        ai_map = {"高": 5, "中": 3, "低": 1}
        ai_score = ai_map.get(ai_suggested, 3)
        total = rule_score + ai_score
        if total >= 7:
            return "高"
        elif total >= 4:
            return "中"
        else:
            return "低"

# 为了导入models，需要处理循环引用，这里在函数内导入
from .. import models
priority_service = PriorityService()