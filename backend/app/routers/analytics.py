"""分析路由：题目分析平台 + 做题分析平台。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..schemas import (
    AccuracyOut,
    ByTypeOut,
    PracticeOverviewOut,
    QuestionsOverviewOut,
    RecentOut,
    TrendOut,
)
from ..services import stats

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/questions/overview", response_model=QuestionsOverviewOut)
def questions_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return QuestionsOverviewOut(**stats.questions_overview(db, current_user.id))


@router.get("/questions/accuracy", response_model=AccuracyOut)
def questions_accuracy(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return AccuracyOut(**stats.questions_accuracy(db, current_user.id, limit))


@router.get("/practice/overview", response_model=PracticeOverviewOut)
def practice_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return PracticeOverviewOut(**stats.practice_overview(db, current_user.id))


@router.get("/practice/trend", response_model=TrendOut)
def practice_trend(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TrendOut(**stats.practice_trend(db, current_user.id, days))


@router.get("/practice/by-type", response_model=ByTypeOut)
def practice_by_type(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ByTypeOut(**stats.practice_by_type(db, current_user.id))


@router.get("/practice/recent", response_model=RecentOut)
def practice_recent(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return RecentOut(**stats.recent_sessions(db, current_user.id, limit))
