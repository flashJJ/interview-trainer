"""掌握度路由：多维度掌握度、雷达数据、薄弱项。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..schemas import (
    MasteryDimensionOut,
    MasteryOverviewOut,
    MasteryRadarOut,
    MasteryWeakOut,
)
from ..services import mastery as mastery_service

router = APIRouter(prefix="/mastery", tags=["mastery"])


@router.get("/overview", response_model=MasteryOverviewOut)
def overview(
    threshold: float = Query(default=0.6, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MasteryOverviewOut(**mastery_service.overview(db, current_user.id, threshold))


@router.get("/dimensions", response_model=MasteryDimensionOut)
def dimensions(
    dim: str = Query(default="q_type", pattern="^(q_type|difficulty|entry)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MasteryDimensionOut(**mastery_service.dimension_stats(db, current_user.id, dim))


@router.get("/radar", response_model=MasteryRadarOut)
def radar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MasteryRadarOut(**mastery_service.radar(db, current_user.id))


@router.get("/weak-points", response_model=MasteryWeakOut)
def weak_points(
    threshold: float = Query(default=0.6, ge=0.0, le=1.0),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MasteryWeakOut(**mastery_service.weak_points(db, current_user.id, threshold, limit))
