from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from ..services.yandex import YandexService
from ..schemas.auth import YandexRefreshRequest, YandexTokenResponse
from ..services.token_manager import verify_token, generate_access_jwt, generate_refresh_jwt
from ..dependencies import get_yandex_service
import logging

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger(__name__)

@router.get(
    "/yandex/login",
    summary="Инициировать OAuth-авторизацию через Яндекс",
    response_description="URL для авторизации",
    responses={
        200: {"description": "URL для авторизации успешно получен"},
        400: {"description": "Ошибка инициализации OAuth"},
        500: {"description": "Ошибка сервера"}
    }
)
async def login_yandex():
    """
    Инициирует процесс OAuth-авторизации через Яндекс.
    
    Возвращает:
    - Объект с URL для перенаправления на страницу авторизации Яндекс
    """
    try:
        auth_data = await YandexService.get_auth_url()
        return auth_data
    except Exception as e:
        log.error(f"Yandex login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to initiate Yandex OAuth"
        )

@router.get(
    "/yandex/callback",
    summary="Обработчик callback от Яндекс OAuth",
    response_description="Токены доступа",
    responses={
        200: {"description": "Авторизация прошла успешно"},
        400: {"description": "Неверный код авторизации"},
        401: {"description": "Ошибка авторизации"},
        500: {"description": "Ошибка сервера"}
    }
)
async def auth_callback(
    code: str,
    request: Request,    
    service: YandexService = Depends(get_yandex_service),
):
    """
    Обрабатывает callback от Яндекс OAuth после успешной авторизации.
    
    Параметры:
    - code: Временный код авторизации от Яндекс OAuth
    
    Возвращает:
    - Объект с access и refresh токенами
    """
    try:
        log.debug(f"Processing callback with code: {code}")
        
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        log.debug(f"Request from IP: {client_ip}, UA: {user_agent}")

        tokens = await service.handle_callback(code)
        
        return {
            "status": "success",
            "tokens": tokens
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Callback processing failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to process OAuth callback"
        )
    
@router.post(
    "/refresh",
    response_model=YandexTokenResponse,
    summary="Обновить токен доступа",
    response_description="Новые токены доступа",
    responses={
        200: {"description": "Токены успешно обновлены"},
        400: {"description": "Неверные данные в токене"},
        401: {"description": "Токен истек"},
        403: {"description": "Недействительный токен"},
        500: {"description": "Ошибка сервера"}
    }
)
async def refresh_token(request: YandexRefreshRequest):
    """
    Обновляет access token с помощью valid refresh token.
    
    Параметры:
    - refresh_token: Действительный refresh token
    
    Возвращает:
    - Новые access и refresh токены
    """
    try:
        log.debug(f"refresh_token {request.refresh_token}")
        payload = verify_token(request.refresh_token)
        
        user_id = payload.get("sub")
        yandex_id = payload.get("yandex_id")

        if not user_id or not yandex_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token payload: missing required claims"
            )

        access_token = generate_access_jwt(user_id, yandex_id)
        refresh_token = generate_refresh_jwt(user_id, yandex_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again."
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid refresh token: {str(e)}"
        )
    except Exception as e:
        log.error(f"Token refresh failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during token refresh"
        )
