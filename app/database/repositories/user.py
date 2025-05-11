import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload  # Ensure both are imported

from app.database.tracker import Tracker  # Import Tracker for return type
from app.schemas.auth import YandexTokenResponse
from app.schemas.yandex import YandexIdInfo

from ...schemas.user import YandexUserInfo
from ..user import User
from ..user_tracker_role import RoleEnum, UserTrackerRole  # Import RoleEnum

log = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        """Получить пользователя по ID"""
        log.debug(f"userid {(user_id)}")
        result = await self.session.execute(select(User).where(User.id == user_id))
        log.debug(f"result {result}")
        return result.scalar_one_or_none()

    async def get_by_id_with_all_trackers(self, user_id: int) -> User | None:
        """Получить пользователя по ID со всеми связанными трекерами"""
        result = await self.session.execute(
            select(User)
            .options(
                selectinload(User.tracker_associations).joinedload(
                    UserTrackerRole.tracker
                )
            )
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_current_tracker(
        self, user_id: int
    ) -> tuple[Tracker, str] | None:
        """Получить текущий активный трекер пользователя и роль пользователя"""
        result = await self.session.execute(
            select(Tracker, UserTrackerRole.role)
            .join(UserTrackerRole, UserTrackerRole.tracker_id == Tracker.id)
            .where(
                UserTrackerRole.user_id == user_id, UserTrackerRole.is_current.is_(True)
            )
        )
        row = result.first()
        if not row:
            return None

        tracker, role = row
        return tracker, role.value

    async def get_by_email(self, email: str) -> User | None:
        """Получить пользователя по email"""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_yandex_id(self, yandex_id: int) -> User | None:
        """Получить пользователя по Yandex ID"""
        result = await self.session.execute(
            select(User).where(User.yandex_id == yandex_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update_from_yandex_id(
        self, user_info: YandexIdInfo, token_data: YandexTokenResponse
    ) -> User:
        """Создает или обновляет пользователя из данных Яндекса"""
        user = await self.get_by_yandex_id(user_info.id)

        if not user:
            user = User(
                email=user_info.default_email,
                yandex_id=user_info.id,
                is_verified=True,
                created_at=datetime.utcnow(),
            )
            self.session.add(user)

        user.yandex_token = token_data.access_token
        user.yandex_refresh_token = token_data.refresh_token
        user.yandex_token_expires = datetime.utcnow() + timedelta(
            seconds=token_data.expires_in
        )
        user.first_name = user_info.first_name
        user.last_name = user_info.last_name
        user.display_name = user_info.display_name
        user.login = user_info.login
        user.is_active = True
        user.is_superuser = False
        user.is_verified = True
        user.last_login = datetime.utcnow()
        user.updated_at = datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_yandex_tokens(
        self,
        user_id: int,
        access_token: str,
        refresh_token: str | None,
        expires_in: int,
    ) -> User | None:
        """Обновить Yandex-токены пользователя"""
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                yandex_token=access_token,
                yandex_refresh_token=refresh_token,
                yandex_token_expires=expires_at,
            )
        )
        await self.session.commit()
        return await self.get_by_id(user_id)

    async def update_user(self, user_id: int, user_info: YandexUserInfo) -> User | None:
        user_info_dict = user_info.model_dump(
            exclude_none=True, exclude={"cloud_id", "org_id"}
        )
        log.debug(f"user_info_dict {user_info_dict}")
        await self.session.execute(
            update(User).where(User.id == user_id).values(**user_info_dict)
        )
        await self.session.commit()
        return await self.get_by_id(user_id)

    async def set_current_tracker(
        self, user_id: int, tracker_id: int, role: str = "employee"
    ) -> User | None:
        """Устанавливает указанный трекер как текущий для пользователя и назначает роль."""

        # Шаг 1: Снять флаг is_current со всех текущих связей пользователя
        await self.session.execute(
            update(UserTrackerRole)
            .where(UserTrackerRole.user_id == user_id)
            .values(is_current=False)
        )

        # Шаг 2: Найти или создать связь для указанного трекера
        existing_assoc_stmt = await self.session.execute(
            select(UserTrackerRole).where(
                UserTrackerRole.user_id == user_id,
                UserTrackerRole.tracker_id == tracker_id,
            )
        )
        assoc = existing_assoc_stmt.scalar_one_or_none()

        if assoc:
            assoc.role = RoleEnum[role]
            assoc.is_current = True
        else:
            assoc = UserTrackerRole(
                user_id=user_id,
                tracker_id=tracker_id,
                role=RoleEnum[role],
                is_current=True,
            )
            self.session.add(assoc)

        await self.session.commit()
        await self.session.refresh(
            assoc
        )  # Refresh the association to get any DB-side updates

        # Вернуть пользователя со всеми его трекерами (включая обновленный текущий)
        return await self.get_by_id_with_all_trackers(user_id)

    async def get_user_role_for_tracker(
        self, user_id: int, tracker_id: int
    ) -> str | None:
        """Получить роль пользователя для указанного трекера"""
        result = await self.session.execute(
            select(UserTrackerRole.role).where(
                UserTrackerRole.user_id == user_id,
                UserTrackerRole.tracker_id == tracker_id,
            )
        )
        role = result.scalar_one_or_none()
        if role:
            return role.value
        return None

    async def get_all_users(self) -> list[User]:
        """Получить всех пользователей"""
        result = await self.session.execute(select(User))
        return result.scalars().all()
        
    async def remove_user_tracker_role(self, user_id: int, tracker_id: int) -> None:
        """Удалить связь между пользователем и трекером"""
        log.debug(f"Removing tracker role for user_id={user_id}, tracker_id={tracker_id}")
        stmt = await self.session.execute(
            select(UserTrackerRole).where(
                UserTrackerRole.user_id == user_id,
                UserTrackerRole.tracker_id == tracker_id,
            )
        )
        user_tracker_role = stmt.scalar_one_or_none()
        
        if user_tracker_role:
            await self.session.delete(user_tracker_role)
            await self.session.commit()
            log.info(f"Removed tracker role for user_id={user_id}, tracker_id={tracker_id}")
        else:
            log.warning(f"No tracker role found for user_id={user_id}, tracker_id={tracker_id}")

    async def change_user_role(
        self, user_id: int, tracker_id: int, new_role: RoleEnum
    ) -> User | None:
        """Изменить роль пользователя для указанного трекера"""
        stmt = await self.session.execute(
            select(UserTrackerRole).where(
                UserTrackerRole.user_id == user_id,
                UserTrackerRole.tracker_id == tracker_id,
            )
        )
        user_tracker_role = stmt.scalar_one_or_none()

        if user_tracker_role:
            user_tracker_role.role = new_role
            user_tracker_role.updated_at = datetime.utcnow()
            await self.session.commit()
            return user_tracker_role
        return None
