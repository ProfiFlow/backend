from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.tracker import TrackerResponse


class YandexUserInfo(BaseModel):
    login: str
    tracker_id: Optional[int] = Field(alias="trackerUid")
    yandex_id: Optional[int] = Field(alias="passportUid")
    first_name: Optional[str] = Field(alias="firstName")
    last_name: Optional[str] = Field(alias="lastName")
    display_name: Optional[str] = Field(alias="display")
    email: Optional[str]


class UserModel(BaseModel):
    self: str
    uid: int
    login: str
    trackerUid: int
    passportUid: Optional[int] = None
    cloudUid: Optional[str] = None
    firstName: str
    lastName: str
    display: str
    email: str
    external: bool
    hasLicense: bool
    dismissed: bool
    useNewFilters: bool
    disableNotifications: bool
    firstLoginDate: Optional[str] = None
    lastLoginDate: Optional[str] = None
    welcomeMailSent: Optional[bool] = None
    sources: List[str]


class UserBaseResponse(BaseModel):
    id: int
    login: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    class Config:
        from_attributes = True


class UserResponse(UserBaseResponse):
    current_tracker: Optional[TrackerResponse] = None
    trackers: List[TrackerResponse] = []
    is_active: bool


class RoleUpdateRequest(BaseModel):
    """Схема для запроса на обновление роли пользователя"""

    role: str = Field(..., description="Роль пользователя (manager или employee)")
