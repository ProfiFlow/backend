from pydantic import BaseModel


class YandexIdInfo(BaseModel):
    id: int
    login: str
    first_name: str
    last_name: str
    display_name: str
    client_id: str
    default_email: str
    real_name: str
