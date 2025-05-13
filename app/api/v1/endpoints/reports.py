from fastapi import APIRouter, HTTPException, status, Depends

from app.api.deps import DB, CurrentUserId, ReportSvc, TrackerSvc, UserRepo, get_current_user_id, get_db, get_report_service, get_tracker_service, get_user_repo
from app.database.user import User
from app.schemas.sprint_report import SprintReportRequest, SprintReport
from app.schemas.team_report import TeamSprintReportRequest, TeamSprintReport
import logging

log = logging.getLogger(__name__)

router = APIRouter()

@router.post("", response_model=SprintReport)
async def generate_sprint_report(
    request: SprintReportRequest,
    db: DB,
    reports: ReportSvc,
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
):
    """
    Generate a sprint report for an employee.
    """
    try:
        user = await user_repo.get_by_id(current_user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        report = await reports.generate_sprint_report(
            user=user,
            sprint_id=request.sprint_id,
            current_user_id=current_user_id,
        )
        return report
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"ML Service unavailable: {e}")
    except Exception as e:
        log.error(f"Error generating sprint report: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating report: {str(e)}")


@router.post("/team", response_model=TeamSprintReport)
async def generate_team_sprint_report(
    request: TeamSprintReportRequest,
    db: DB,
    reports: ReportSvc,
    current_user_id: CurrentUserId,
) -> TeamSprintReport:
    """
    Generate a sprint report for the entire team.
    """
    try:
        report = await reports.generate_team_sprint_report(
            current_user_id=current_user_id,
            sprint_id=request.sprint_id,
        )
        return report
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"ML Service unavailable: {e}")
    except Exception as e:
        log.error(f"Error generating team sprint report: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate team report")


@router.get("/sprints")
async def get_sprints_for_current_tracker(
    tracker_service: TrackerSvc,
    user_repo: UserRepo,
    current_user_id: CurrentUserId,
):
    """
    Получить список спринтов текущего трекера пользователя
    """
    tracker_info = await user_repo.get_user_current_tracker(current_user_id)
    if not tracker_info:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь не привязан к трекеру")
    
    sprints = await tracker_service.get_sprints(current_user_id)
    return sprints 
