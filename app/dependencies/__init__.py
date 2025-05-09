from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.yandex import YandexService
from ..database import get_db
from .auth import get_current_user

async def get_yandex_service(db: AsyncSession = Depends(get_db)) -> YandexService:
    return YandexService(db)