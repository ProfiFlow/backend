from pydantic import BaseModel

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None

# Модель запроса
class RefreshRequest(BaseModel):
    refresh_token: str