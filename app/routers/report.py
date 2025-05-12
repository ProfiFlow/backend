from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.database.repositories.user import UserRepository
from app.routers import user
from app.schemas.sprint_report import SprintReportRequest, SprintReport
from app.schemas.team_report import TeamSprintReportRequest, TeamSprintReport
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])

report_generator = ReportService()

@router.post("/sprint", response_model=SprintReport)
async def generate_sprint_report(
    request: SprintReportRequest,
    session: AsyncSession = Depends(get_db),
    current_user_id: user.User = Depends(user.get_current_user),
):
    """
    Generate a sprint report for an employee.
    """
    try:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        report = await report_generator.generate_sprint_report(
            db=session,
            current_user_id=current_user_id,
            user=user,
            sprint_id=request.sprint_id,
        )
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"ML Service unavailable: {e}")
    except Exception as e:
        print(f"Error generating sprint report: {e}") # Log the error
        raise HTTPException(status_code=500, detail="Failed to generate report due to an internal error.")


@router.post("/team/sprint", response_model=TeamSprintReport)
async def generate_team_sprint_report(
    request: TeamSprintReportRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Generate a sprint report for the entire team.
    """
    try:
        report = await report_generator.generate_team_sprint_report(
            db=session,
            sprint_number=request.sprint_number,
        )
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"ML Service unavailable: {e}")
    except Exception as e:
        print(f"Error generating team sprint report: {e}") # Log the error
        raise HTTPException(status_code=500, detail="Failed to generate team report due to an internal error.") 
