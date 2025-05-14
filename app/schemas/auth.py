from pydantic import BaseModel


class YandexTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None


class YandexRefreshRequest(BaseModel):
    refresh_token: str
