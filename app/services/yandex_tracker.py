import base64
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.yandex import YandexIdInfo

from ..config import settings
from ..database.repositories.user import UserRepository
from ..database.user import User
from ..schemas.auth import YandexTokenResponse
from ..schemas.user import YandexUserInfo
from .token_manager import generate_access_jwt, generate_refresh_jwt

log = logging.getLogger(__name__)


class YandexTrackerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def _make_yandex_tracker_request(
        self, method: str, url: str, access_token: str, org_id: str, data: dict = None
    ):
        """Общий метод для запросов к Яндекс API"""
        try:
            log.debug(f"Making request to Yandex Tracker: {method} {url}")
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method,
                    url,
                    headers={
                        "Authorization": f"OAuth {access_token}",
                        "X-Org-ID": org_id,
                        "X-Cloud-Org-ID": org_id,
                    },
                    timeout=10.0,
                    json=data,
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительный или просроченный токен Яндекс.Трекера",
                )
            elif e.response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Недостаточно прав для выполнения операции",
                )
            elif e.response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Запрашиваемый ресурс не найден",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Сервис Яндекс.Трекера временно недоступен",
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Превышено время ожидания ответа от Яндекс.Трекера",
            )

    async def _get_user_with_valid_token(self, user_id: int) -> User:
        """Получает пользователя и обновляет токен при необходимости"""
        try:
            user = await self.user_repo.get_by_id(user_id)
            tracker = await self.user_repo.get_user_current_tracker(user_id)
            if tracker:
                user.org_id = tracker[0].yandex_org_id or tracker[0].yandex_cloud_id
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Пользователь не найден",
                )
            if not user.yandex_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Токен Яндекс не привязан к учетной записи",
                )

            if self._is_token_expired(user.yandex_token_expires):
                if not user.yandex_refresh_token:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Отсутствует refresh token для обновления",
                    )
                return await self._refresh_and_update_user_tokens(user)
            return user

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка проверки токена пользователя: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при проверке токена",
            )

    async def _refresh_and_update_user_tokens(self, user: User) -> User:
        """Обновляет токены пользователя"""
        try:
            new_tokens = await self._refresh_token(user.yandex_refresh_token)
            return await self.user_repo.update_yandex_tokens(
                user.id,
                new_tokens.access_token,
                new_tokens.refresh_token,
                timedelta(seconds=new_tokens.expires_in),
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка обновления токенов: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при обновлении токенов",
            )

    async def get_users(self, user_id: int):
        """Получение списка пользователей трекера"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен",
                )
            return await self._make_yandex_tracker_request(
                "GET",
                "https://api.tracker.yandex.net/v2/users",
                user.yandex_token,
                user.org_id,
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения пользователей: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении списка пользователей",
            )

    def _is_token_expired(self, expires_at: datetime) -> bool:
        """Проверяет истёк ли срок действия токена"""
        return datetime.utcnow() > expires_at if expires_at else True

    async def _refresh_and_update_user_tokens(self, user: User) -> User:
        """Обновляет токены пользователя"""
        try:
            new_tokens = await self._refresh_token(user.yandex_refresh_token)
            return await self.user_repo.update_yandex_tokens(
                user.id,
                new_tokens.access_token,
                new_tokens.refresh_token,
                timedelta(seconds=new_tokens.expires_in),
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка обновления токенов: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при обновлении токенов",
            )
