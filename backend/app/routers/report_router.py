from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..database import get_db
from .. import models, auth, schemas
from ..services.report_service import report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.get("/")
def get_report(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin_user)  # 仅父节点可查看
):
    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    if start > end:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    report = report_service.generate_report(db, start, end)
    return report

@router.get("/weekly")
def get_weekly_report(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin_user)
):
    end = datetime.utcnow()
    start = end - timedelta(days=7)
    report = report_service.generate_report(db, start, end)
    return report

@router.get("/monthly")
def get_monthly_report(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin_user)
):
    end = datetime.utcnow()
    start = end - timedelta(days=30)
    report = report_service.generate_report(db, start, end)
    return report