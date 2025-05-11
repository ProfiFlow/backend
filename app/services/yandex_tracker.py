from ..schemas.yandex_tracker import Task
import base64
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.yandex import YandexIdInfo
from app.schemas.yandex_tracker import Sprint

from ..config import settings
from ..database.repositories.user import UserRepository
from ..database.user import User
from ..schemas.auth import YandexTokenResponse
from ..schemas.user import YandexUserInfo
from .token_manager import generate_access_jwt, generate_refresh_jwt
from isodate import parse_duration

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
                log.error(f"Ошибка при запросе к Яндекс.Трекеру: {e}")
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
        
    async def get_sprints(self, user_id: int):
        """Получение списка спринтов трекера"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен",
                )
            return await self._make_yandex_tracker_request(
                "GET",
                "https://api.tracker.yandex.net/v2/sprints",
                user.yandex_token,
                user.org_id,
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения спринтов: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении списка спринтов",
            )

    async def get_sprint_tasks(self, sprint_id: int, user_id: int, assignee_user_login: str) -> Task:
        """Получение списка задач спринта"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен",
                )
            log.debug(
                f"Getting tasks for sprint {sprint_id} assigned to user {assignee_user_login}"
            )
            return [
                Task(**task)
                for task in await self._make_yandex_tracker_request(
                    "POST",
                    "https://api.tracker.yandex.net/v3/issues/_search",
                    user.yandex_token,
                    user.org_id,
                    {
                        "filter": {
                            "sprint": sprint_id,
                            "assignee": assignee_user_login,
                            "type": "task",
                        },
                    },
                )
            ]
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения задач спринта: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении списка задач спринта",
            )

    async def get_sprint(self, sprint_id: int, user_id: int) -> Sprint:
        """Получение информации о спринте"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен",
                )
            return Sprint(**await self._make_yandex_tracker_request(
                "GET",
                f"https://api.tracker.yandex.net/v3/sprints/{sprint_id}",
                user.yandex_token,
                user.org_id,
            ))
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения информации о спринте: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении информации о спринте",
            )
        
    async def get_issue_logged_time(
        self, issue_id: str, user_id: int
    ) -> float:
        """Получение информации о затраченном времени на задачу"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен",
                )
            worklog_entries = await self._make_yandex_tracker_request(
                "GET",
                f"https://api.tracker.yandex.net/v3/issues/{issue_id}/worklog",
                user.yandex_token,
                user.org_id,
            )
            
            total_seconds = 0
            
            for entry in worklog_entries:
                duration = entry.get('duration', '')
                if not duration:
                    continue
                
                try:
                    duration_obj = parse_duration(duration)
                    if hasattr(duration_obj, 'total_seconds'):
                        seconds = duration_obj.total_seconds()
                    else:
                        # For Duration objects, we need to approximate
                        seconds = duration_obj.days * 24 * 3600 + duration_obj.seconds
                    
                    total_seconds += seconds
                except ValueError:
                    continue
            
            total_hours = round(total_seconds / 3600, 1)
            return total_hours
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения информации о затраченном времени: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении информации о затраченном времени",
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
