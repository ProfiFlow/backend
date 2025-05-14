import logging
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from jose import JWTError, jwt

from ..config import settings

logger = logging.getLogger(__name__)


def verify_token(token: str) -> dict:
    """
    Валидирует JWT токен и возвращает его payload

    Args:
        token: JWT токен из заголовка Authorization

    Returns:
        dict: Декодированный payload токена

    Raises:
        HTTPException: Если токен невалиден или истек срок действия
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Декодируем токен

        logger.debug(f"token {token}|{settings.secret_key}|{[settings.algorithm]}")
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        logger.debug(f"payload {payload}")

        # Проверяем обязательные поля
        if payload.get("sub") is None:
            logger.warning("Token missing 'sub' claim")
            raise credentials_exception

        # Проверяем срок действия
        expire = payload.get("exp")
        if expire is None:
            logger.warning("Token missing 'exp' claim")
            raise credentials_exception

        if datetime.utcnow() > datetime.fromtimestamp(expire):
            logger.warning(f"Token expired at {datetime.fromtimestamp(expire)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
            )

        return payload

    except JWTError as e:
        logger.error(f"JWT validation error: {str(e)}")
        raise credentials_exception from e


def generate_access_jwt(user_id: str, yandex_id: str) -> str:
    """Генерация JWT токена"""
    payload = {
        "sub": str(user_id),
        "yandex_id": str(yandex_id),
        "exp": datetime.utcnow()
        + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def generate_refresh_jwt(user_id: str, yandex_id: str) -> str:
    """Генерация JWT токена"""
    payload = {
        "sub": str(user_id),
        "yandex_id": str(yandex_id),
        "exp": datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
