from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MetricWithComparison(BaseModel):
    current: float
    previous: Optional[float] = None
    change_percent: Optional[float] = None


class EmployeeSprintStats(BaseModel):
    employee_id: str
    employee_name: str
    story_points_closed: MetricWithComparison
    tasks_completed: MetricWithComparison
    deadlines_missed: MetricWithComparison
    average_task_completion_time: MetricWithComparison
    rating: int = Field(..., ge=1, le=5)  # Rating from 1 to 5
    rating_explanation: str


class TeamSprintReport(BaseModel):
    sprint_id: int
    sprint_start_date: datetime
    sprint_end_date: datetime
    employee_stats: List[EmployeeSprintStats]


class TeamSprintReportRequest(BaseModel):
    sprint_id: int
