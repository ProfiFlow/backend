from datetime import datetime, timedelta
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from .user import User

async def create_or_update_user(
    db: AsyncSession,
    yandex_id: str,
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None
) -> User:
    # Асинхронный запрос к БД
    result = await db.execute(select(User).where(User.yandex_id == yandex_id))
    user = result.scalars().first()
    
    if user:
        # Обновляем существующего пользователя
        user.access_token = access_token
        user.refresh_token = refresh_token
        if expires_in:
            user.token_expires = datetime.utcnow() + timedelta(seconds=expires_in)
    else:
        # Создаем нового пользователя
        user = User(
            id=yandex_id,
            yandex_id=yandex_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires=datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
        )
        db.add(user)
    
    await db.commit()
    await db.refresh(user)
    return user