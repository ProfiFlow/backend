import httpx
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import base64
from jose import jwt
from ..config import settings
from ..database import get_db
from ..database.user import User
from ..database.repositories.user import UserRepository
from ..schemas.user import YandexUserInfo
from ..schemas.auth import TokenResponse
from .token_manager import generate_access_jwt, generate_refresh_jwt
import logging

log = logging.getLogger(__name__)

class YandexService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def _make_yandex_tracer_request(self, url: str, access_token: str, org_id: str):
        """Общий метод для запросов к Яндекс API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "Authorization": f"OAuth {access_token}",
                        "X-Org-ID": org_id,                         
                        "X-Cloud-Org-ID": org_id
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительный или просроченный токен Яндекс.Трекера"
                )
            elif e.response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Недостаточно прав для выполнения операции"
                )
            elif e.response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Запрашиваемый ресурс не найден"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Сервис Яндекс.Трекера временно недоступен"
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Превышено время ожидания ответа от Яндекс.Трекера"
            )

    async def _make_yandex_request(self, url: str, access_token: str):
        """Общий метод для запросов к Яндекс API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"OAuth {access_token}"},
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительный или просроченный токен Яндекс OAuth"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка при запросе к Яндекс API: {str(e)}"
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Сервис Яндекс OAuth временно недоступен"
            )

    async def _get_token(self, code: str) -> TokenResponse:
        """Получение токенов от Яндекс OAuth"""
        auth_string = f"{settings.yandex_client_id}:{settings.yandex_client_secret}"
        basic_auth = base64.b64encode(auth_string.encode()).decode()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth.yandex.ru/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": settings.yandex_redirect_uri
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": f"Basic {basic_auth}"
                    }
                )
                response.raise_for_status()
                return TokenResponse(**response.json())
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный код авторизации или истек срок его действия"
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Сервис авторизации Яндекс временно недоступен"
            )
        except Exception as e:
            log.error(f"Ошибка получения токена: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка при получении токена"
            )

    async def _refresh_token(self, refresh_token: str) -> TokenResponse:
        """Обновление истёкшего токена Яндекса"""
        auth_string = f"{settings.yandex_client_id}:{settings.yandex_client_secret}"
        basic_auth = base64.b64encode(auth_string.encode()).decode()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth.yandex.ru/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": f"Basic {basic_auth}"
                    }
                )
                response.raise_for_status()
                return TokenResponse(**response.json())
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительный refresh token"
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Сервис авторизации Яндекс временно недоступен"
            )
        except Exception as e:
            log.error(f"Ошибка обновления токена: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка при обновлении токена"
            )

    def _is_token_expired(self, expires_at: datetime) -> bool:
        """Проверяет истёк ли срок действия токена"""
        return datetime.utcnow() > expires_at if expires_at else True

    @staticmethod
    async def get_auth_url(state: str = None) -> dict:
        """Генерация URL для авторизации через Яндекс"""
        try:
            params = {
                "response_type": "code",
                "client_id": settings.yandex_client_id,
                "redirect_uri": settings.yandex_redirect_uri,
                "scope": "tracker:read tracker:write"
            }
            if state:
                params["state"] = state
                
            return {
                "auth_url": f"https://oauth.yandex.ru/authorize?{httpx.QueryParams(params)}",
                "state": state
            }
        except Exception as e:
            log.error(f"Ошибка генерации auth URL: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при генерации URL авторизации"
            )
    
    async def handle_callback(self, code: str) -> TokenResponse:
        """Обработка callback после авторизации через Яндекс"""
        try:
            token_data = await self._get_token(code)
            user_info = await self._get_user_info(token_data.access_token)
            
            user = await self.user_repo.create_or_update_from_yandex(
                yandex_id=int(user_info["id"]),
                email=user_info.get("default_email", None),
                access_token=token_data.access_token,
                refresh_token=token_data.refresh_token,
                expires_in=token_data.expires_in
            )
            
            return TokenResponse(
                access_token=generate_access_jwt(user.id, user.yandex_id),
                refresh_token=generate_refresh_jwt(user.id, user.yandex_id),
                token_type="bearer",
                expires_in=settings.access_token_expire_minutes * 60,
                yandex_id=user.yandex_id
            )
            
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка обработки callback: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при обработке авторизации"
            )
    
    async def _get_user_info(self, token: str) -> dict:
        """Получение информации о пользователе по токену после авторизации"""
        try:
            return await self._make_yandex_request(
                "https://login.yandex.ru/info",
                token
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения информации о пользователе: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении данных пользователя"
            )

    async def _get_user_with_valid_token(self, user_id: int) -> User:
        """Получает пользователя и обновляет токен при необходимости"""
        try:
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Пользователь не найден"
                )
            if not user.yandex_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Токен Яндекс не привязан к учетной записи"
                )

            if self._is_token_expired(user.yandex_token_expires):
                if not user.yandex_refresh_token:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Отсутствует refresh token для обновления"
                    )
                return await self._refresh_and_update_user_tokens(user)
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка проверки токена пользователя: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при проверке токена"
            )

    async def _refresh_and_update_user_tokens(self, user: User) -> User:
        """Обновляет токены пользователя"""
        try:
            new_tokens = await self._refresh_token(user.yandex_refresh_token)
            return await self.user_repo.update_yandex_tokens(
                user.id,
                new_tokens.access_token,
                new_tokens.refresh_token,
                timedelta(seconds=new_tokens.expires_in)
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка обновления токенов: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при обновлении токенов"
            )
    
    async def set_org_id(self, user_id: int, org_id: str) -> User:
        """Установка organization_id для пользователя"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Пользователь не найден"
                )
            return await self.user_repo.set_org_id(user_id, org_id)
            
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка установки org_id: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при установке organization_id"
            )
        
    async def get_user_profile(self, user_id: int) -> User:
        """Получение профиля пользователя из Яндекс API"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен"
                )
                
            profile = await self._make_yandex_tracer_request(
                "https://api.tracker.yandex.net/v2/myself",
                user.yandex_token,
                user.org_id
            )
            return await self.user_repo.update_user(user_id, YandexUserInfo(**profile))
            
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения профиля: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении профиля пользователя"
            )
        
    async def get_queues(self, user_id: int):
        """Получение списка очередей"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен"
                )
            return await self._make_yandex_tracer_request(
                "https://api.tracker.yandex.net/v2/queues",
                user.yandex_token,
                user.org_id
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения очередей: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении списка очередей"
            )
        
    async def get_queue(self, user_id: int, queue_id: int):
        """Получение информации об очереди"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен"
                )
            return await self._make_yandex_tracer_request(
                f"https://api.tracker.yandex.net/v2/queues/{queue_id}",
                user.yandex_token,
                user.org_id
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения очереди: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении информации об очереди"
            )
        
    async def get_users(self, user_id: int):
        """Получение списка пользователей трекера"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен"
                )
            return await self._make_yandex_tracer_request(
                "https://api.tracker.yandex.net/v2/users",
                user.yandex_token,
                user.org_id
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения пользователей: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении списка пользователей"
            )
        
    async def get_boards(self, user_id: int):
        """Получение списка досок"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен"
                )
            return await self._make_yandex_tracer_request(
                "https://api.tracker.yandex.net/v2/boards",
                user.yandex_token,
                user.org_id
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения досок: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении списка досок"
            )
        
    async def get_issues(self, user_id: int):
        """Получение списка задач"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен"
                )
            return await self._make_yandex_tracer_request(
                "https://api.tracker.yandex.net/v2/issues",
                user.yandex_token,
                user.org_id
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения задач: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении списка задач"
            )
        
    async def get_issue(self, user_id: int, issue_key: str):
        """Получение информации о задаче"""
        try:
            user = await self._get_user_with_valid_token(user_id)
            if not user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID не установлен"
                )
            return await self._make_yandex_tracer_request(
                f"https://api.tracker.yandex.net/v2/issues/{issue_key}",
                user.yandex_token,
                user.org_id
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Ошибка получения задачи: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении информации о задаче"
            )