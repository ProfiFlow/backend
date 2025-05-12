from typing import List
from datetime import date, datetime
from pydantic import BaseModel
from app.schemas.team_report import MetricWithComparison
from app.schemas.recommendation import Recommendation

class SprintReport(BaseModel):
    user_id: int
    employee_name: str
    sprint_name: str
    sprint_start_date: date
    sprint_end_date: date
    story_points_closed: MetricWithComparison
    tasks_completed: MetricWithComparison
    deadlines_missed: MetricWithComparison
    average_task_completion_time: MetricWithComparison  # in hours
    activity_analysis: str | None
    recommendations: List[Recommendation] | None = []

class SprintReportRequest(BaseModel):
    sprint_id: int 
