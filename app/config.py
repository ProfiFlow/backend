from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Основные настройки API (с обратной совместимостью)
    project_name: str = "ProfiFlow"
    api_v1_str: str = "/api/v1"
    cors_origins: List[str] = ["*"]

    # Стандартные настройки (нижний регистр для обратной совместимости)
    yandex_client_id: str
    yandex_client_secret: str
    yandex_redirect_uri: str
    database_url: str
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    yc_folder_id: str
    yc_api_key: str | None = None
    yc_iam_token: str | None = None
    yc_gpt_model: str = "yandexgpt"
    yc_gpt_version: str = "rc"
    yc_gpt_temperature: float = 0.5
    yc_gpt_max_tokens: int = 1000

    class Config:
        env_file = ".env"


settings = Settings()
