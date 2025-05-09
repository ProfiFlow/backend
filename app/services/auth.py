from datetime import datetime, timedelta
from logging import log
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException
from jose import jwt
import httpx
import base64
from ..config import settings
from ..database import crud, get_db
from ..schemas.auth import YandexTokenResponse
from ..database.user import User
from ..database.repositories.user import UserRepository
import logging
log = logging.getLogger("app")

class YandexAuthService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.user_repo = UserRepository(self.db)

    @staticmethod
    async def get_auth_url(state: str = None) -> dict:
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
    
    # @staticmethod
    # async def get_auth_url():
    #     return {
    #         "auth_url": (
    #             f"https://oauth.yandex.ru/authorize?response_type=code"
    #             f"&client_id={settings.yandex_client_id}"
    #             f"&redirect_uri={settings.yandex_redirect_uri}"
    #             f"&scope=tracker:read&scope=tracker:write"
    #         )
    #     }

    async def handle_callback(self, code: str) -> YandexTokenResponse:
        try:
            # 1. Получаем токены от Яндекса
            token_data = await self._get_yandex_tokens(code)
            
            # 2. Получаем информацию о пользователе
            user_info = await self._get_yandex_user_info(token_data["access_token"])
            
            # 3. Сохраняем/обновляем пользователя через репозиторий
            user = await self.user_repo.create_or_update_from_yandex_id(
                yandex_id=user_info["id"],
                email=user_info.get("default_email"),
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                expires_in=token_data["expires_in"]
            )
            
            # 4. Генерируем наш JWT
            jwt_token = self._generate_jwt(user)
            
            return YandexTokenResponse(
                access_token=jwt_token,
                token_type="bearer",
                expires_in=settings.access_token_expire_minutes * 60,
                yandex_id=user.yandex_id
            )
            
        except Exception as e:
            log.error(f"Auth error: {str(e)}", exc_info=True)
            raise

    # Вспомогательные методы
    async def _get_yandex_tokens(self, code: str) -> dict:
        """Получение токенов от Яндекс OAuth"""
        auth_string = f"{settings.yandex_client_id}:{settings.yandex_client_secret}"
        basic_auth = base64.b64encode(auth_string.encode()).decode()
        
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
            return response.json()

    async def _get_yandex_user_info(self, token: str) -> User:
        """Получение информации о пользователе"""
        async with httpx.AsyncClient() as client:
            user_response = await client.get(
                "https://login.yandex.ru/info",
                headers={"Authorization": f"OAuth {token}"}
            )
            
            user_response.raise_for_status()
            user_info = user_response.json()
            return user_info
        
    def _generate_jwt(self, user: User) -> str:
        """Генерация JWT токена"""
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "yandex_id": user.yandex_id,
            "exp": datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        }
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    
    async def handle_callback(code: str):
        try:
            # 1. Получаем токен у Яндекс OAuth
            auth_string = f"{settings.yandex_client_id}:{settings.yandex_client_secret}"
            basic_auth = base64.b64encode(auth_string.encode()).decode()
            
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.yandex_redirect_uri
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic_auth}"
            }

            async with httpx.AsyncClient() as client:
                # Получаем access_token от Яндекса
                token_response = await client.post(
                    "https://oauth.yandex.ru/token",
                    data=token_data,
                    headers=headers
                )
                
                if token_response.status_code != 200:
                    error_detail = token_response.json().get("error_description", "Unknown error")
                    log.error(f"Ошибка OAuth: {error_detail}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Yandex OAuth error: {error_detail}"
                    )
                
                token_data = token_response.json()

                # 2. Получаем информацию о пользователе
                user_response = await client.get(
                    "https://login.yandex.ru/info",
                    headers={"Authorization": f"OAuth {token_data['access_token']}"}
                )
                
                user_response.raise_for_status()
                user_info = user_response.json()
                log.debug(f'user_info {user_info}')

                # 3. Сохраняем/обновляем пользователя в БД
                user = await crud.create_or_update_user(
                    db=db,
                    yandex_id=user_info["id"],
                    access_token=token_data["access_token"],
                    refresh_token=token_data["refresh_token"],
                    expires_in=token_data["expires_in"]
                )
                db.commit()

                # 4. Генерируем наш JWT токен
                jwt_payload = {
                    "sub": str(user.id),
                    "yandex_id": user.yandex_id,
                    "exp": datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
                }
                
                jwt_token = jwt.encode(
                    jwt_payload,
                    settings.secret_key,
                    algorithm=settings.algorithm
                )

                # 5. Возвращаем токены
                return YandexTokenResponse(
                    access_token=jwt_token,
                    token_type="bearer",
                    expires_in=token_data["expires_in"],
                    refresh_token=token_data.get("refresh_token"),
                    yandex_id=user.yandex_id
                )
                
        except httpx.HTTPStatusError as e:
            log.error(f"HTTP error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=400,
                detail=f"Yandex API error: {e.response.text}"
            )
        except Exception as e:
            log.error(f"Internal error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )
