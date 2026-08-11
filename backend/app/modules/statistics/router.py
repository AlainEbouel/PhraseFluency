from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.statistics import service
from app.modules.statistics.schemas import DashboardOut, DetailedStatisticsOut
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/statistics", tags=["statistics"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.get_dashboard(db, user.id)


@router.get("/detailed", response_model=DetailedStatisticsOut)
def detailed(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.get_detailed_statistics(db, user.id)
