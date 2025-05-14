from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TrackerBase(BaseModel):
    name: str
    tracker_type: str = "yandex"
    yandex_cloud_id: Optional[str] = None
    yandex_org_id: Optional[str] = None


class TrackerCreate(TrackerBase):
    pass


class TrackerResponse(TrackerBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool = True
    role: Optional[str] = None

    class Config:
        from_attributes = True


class TrackerUpdate(BaseModel):
    name: Optional[str] = None
    yandex_cloud_id: Optional[str] = None
    yandex_org_id: Optional[str] = None
    is_active: Optional[bool] = None
