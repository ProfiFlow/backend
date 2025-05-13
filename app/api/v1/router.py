from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.api.deps import DB
from app.api.v1.endpoints import auth, profile, reports, trackers, users

api_router = APIRouter()

# Подключаем все эндпоинты
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(trackers.router, prefix="/trackers", tags=["trackers"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(users.router, prefix="/users", tags=["users"])


@api_router.get("/health", tags=["health"])
async def health_check(db: DB):
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar_one() != 1:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database check failed",
            )
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}",
        )
