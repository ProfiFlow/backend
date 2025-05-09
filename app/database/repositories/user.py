from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from ...schemas.user import YandexUserInfo
from ..user import User
import logging

log = logging.getLogger(__name__)

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        """Получить пользователя по ID"""
        log.debug(f"userid {(user_id)}")
        result = await self.session.execute(
            select(User).where(User.id == user_id)
            )
        log.debug(f"result {result}")
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Получить пользователя по email"""
        result = await self.session.execute(
            select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_yandex_id(self, yandex_id: str) -> User | None:
        """Получить пользователя по Yandex ID"""
        result = await self.session.execute(
            select(User).where(User.yandex_id == yandex_id))
        return result.scalar_one_or_none()
    
    async def create_or_update_from_yandex(
        self,
        yandex_id: str,
        email: str,
        access_token: str,
        refresh_token: str | None,
        expires_in: int
    ) -> User:
        """Создает или обновляет пользователя из данных Яндекса"""
        user = await self.get_by_yandex_id(yandex_id)
        
        if not user:
            user = User(
                email=email,
                yandex_id=yandex_id,
                is_verified=True
            )
            self.session.add(user)
        
        user.yandex_token = access_token
        user.yandex_refresh_token = refresh_token
        user.yandex_token_expires = datetime.utcnow() + timedelta(seconds=expires_in)
        
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_yandex_tokens(
        self,
        user_id: int,
        access_token: str,
        refresh_token: str | None,
        expires_in: int
    ) -> User | None:
        """Обновить Yandex-токены пользователя"""
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                yandex_token=access_token,
                yandex_refresh_token=refresh_token,
                yandex_token_expires=expires_at
            ))
        await self.session.commit()
        return await self.get_by_id(user_id)

    async def update_user(
        self,
        user_id: int,
        user_info: YandexUserInfo
    ) -> User | None:
        user_info_dict = user_info.model_dump(exclude_none=True)
        log.debug(f"user_info_dict {user_info_dict}")
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(**user_info_dict))
        await self.session.commit()
        return await self.get_by_id(user_id)
    
    async def set_org_id(
        self,
        user_id: int,
        org_id: str
    ) -> User | None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(org_id=org_id))
        await self.session.commit()
        return await self.get_by_id(user_id)
    