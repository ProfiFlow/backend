from fastapi import Request, HTTPException, status
from ..services.token_manager import verify_token
from jose import JWTError

async def get_current_user(request: Request):
    """
        Dependency для аутентификации пользователя через JWT токен.
        Возвращает user_id из токена.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = request.headers["authorization"].replace("Bearer ", "")
        payload = verify_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return int(user_id)
    except (KeyError, JWTError):
        raise credentials_exception
