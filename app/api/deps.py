from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.database.repositories.report import ReportRepository, TeamReportRepository
from app.database.repositories.tracker import TrackerRepository
from app.database.repositories.user import UserRepository
from app.services.report_service import ReportService
from app.services.token_manager import verify_token
from app.services.yandex import YandexService
from app.services.yandex_gpt_service import YandexGPTMLService
from app.services.yandex_tracker import YandexTrackerService

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Зависимость для получения сессии БД.
    """
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()

DB = Annotated[AsyncSession, Depends(get_db)]

async def get_current_user_id(request: Request) -> int:
    """
    Dependency для аутентификации пользователя через JWT токен.
    Возвращает user_id из токена.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = request.headers["authorization"].replace("Bearer ", "")
        payload = verify_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return int(user_id)
    except (KeyError, JWTError):
        raise credentials_exception

CurrentUserId = Annotated[int, Depends(get_current_user_id)]

def get_user_repo(db: DB):
    return UserRepository(db)

UserRepo = Annotated[UserRepository, Depends(get_user_repo)]

def get_report_repo(db: DB):
    return ReportRepository(db)

ReportRepo = Annotated[ReportRepository, Depends(get_report_repo)]

def get_team_report_repo(db: DB):
    return TeamReportRepository(db)

TeamReportRepo = Annotated[TeamReportRepository, Depends(get_team_report_repo)]

def get_tracker_repo(db: DB):
    return TrackerRepository(db)

TrackerRepo = Annotated[TrackerRepository, Depends(get_tracker_repo)]

def get_tracker_service(db: DB):
    return YandexTrackerService(db)

TrackerSvc = Annotated[YandexTrackerService, Depends(get_tracker_service)]

def get_gpt_service():
    return YandexGPTMLService()

GPTSvc = Annotated[YandexGPTMLService, Depends(get_gpt_service)]

def get_report_service(db: DB, tracker_service: TrackerSvc, gpt_service: GPTSvc, user_repo: UserRepo, report_repo: ReportRepo, team_report_repo: TeamReportRepo):
    return ReportService(db, tracker_service, gpt_service, user_repo, report_repo, team_report_repo)

ReportSvc = Annotated[ReportService, Depends(get_report_service)]

def get_yandex_service(db: DB):
    return YandexService(db)

YandexSvc = Annotated[YandexService, Depends(get_yandex_service)]
