from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any
from .. import models

class ReportService:
    @staticmethod
    def generate_report(db: Session, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """生成指定时间段内的统计报告"""
        # 需求总数
        total = db.query(models.Requirement).filter(
            models.Requirement.created_at >= start_date,
            models.Requirement.created_at <= end_date
        ).count()
        # 已完成数
        resolved = db.query(models.Requirement).filter(
            models.Requirement.status == models.RequirementStatus.RESOLVED,
            models.Requirement.resolved_at >= start_date,
            models.Requirement.resolved_at <= end_date
        ).count()
        # 平均处理时长（仅统计已解决的）
        avg_seconds = 0
        resolved_requirements = db.query(models.Requirement).filter(
            models.Requirement.status == models.RequirementStatus.RESOLVED,
            models.Requirement.resolved_at >= start_date,
            models.Requirement.resolved_at <= end_date,
            models.Requirement.created_at is not None
        ).all()
        if resolved_requirements:
            total_seconds = 0
            for req in resolved_requirements:
                delta = req.resolved_at - req.created_at
                total_seconds += delta.total_seconds()
            avg_seconds = total_seconds / len(resolved_requirements)
        avg_hours = avg_seconds / 3600 if avg_seconds else 0

        # 各子节点提交数量排行
                # 各子节点提交数量排行（带姓名+部门）
        from sqlalchemy import func
        user_counts = db.query(
            models.Requirement.user_id,
            models.User.username,
            models.User.department,
            func.count(models.Requirement.id).label('count')
        ).join(models.User, models.User.id == models.Requirement.user_id).filter(
            models.Requirement.created_at >= start_date,
            models.Requirement.created_at <= end_date
        ).group_by(models.Requirement.user_id).order_by(func.count(models.Requirement.id).desc()).all()
        user_rank = [
            {"user_id": uid, "username": uname, "department": dept, "count": cnt}
            for uid, uname, dept, cnt in user_counts
        ]


        # 重点需求处理进度
        critical = db.query(models.Requirement).filter(
            models.Requirement.priority == "高",
            models.Requirement.status != models.RequirementStatus.RESOLVED
        ).count()

        # 返回数据
        report = {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total": total,
            "resolved": resolved,
            "completion_rate": round(resolved / total * 100, 2) if total else 0,
            "avg_processing_hours": round(avg_hours, 2),
            "user_ranking": user_rank,
            "pending_critical": critical
        }
        return report

report_service = ReportService()