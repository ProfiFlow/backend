from datetime import date, datetime

from pydantic import BaseModel, Field


class TaskStatus(BaseModel):
    id: str
    key: str
    display: str


class Task(BaseModel):
    id: str
    key: str
    summary: str
    story_points: int | None = Field(alias="storyPoints", default=None)
    deadline: date | None = Field(format="%Y-%m-%d", default=None)
    resolved_at: datetime | None = Field(alias="resolvedAt", default=None)
    status: TaskStatus


class Sprint(BaseModel):
    id: int
    name: str
    board: str
    start_date: date = Field(format="%Y-%m-%d")
    end_date: date = Field(format="%Y-%m-%d")
