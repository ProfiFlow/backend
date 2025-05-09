from pydantic import BaseModel, Field
from typing import List, Optional

class YandexUserInfo(BaseModel):
    login: str
    tracker_id: Optional[int] = Field(alias="trackerUid")
    yandex_id: Optional[int] = Field(alias="passportUid")
    cloud_id: Optional[str] = Field(alias="cloudUid")
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