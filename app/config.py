from pydantic_settings import BaseSettings

class Settings(BaseSettings):
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

    class Config:
        env_file = ".env"

settings = Settings()