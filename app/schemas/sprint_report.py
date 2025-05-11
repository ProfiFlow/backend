from typing import List
from datetime import date, datetime
from pydantic import BaseModel

class Recommendation(BaseModel):
    title: str
    text: str

class SprintReport(BaseModel):
    user_id: int
    employee_name: str
    sprint_name: str
    sprint_start_date: date
    sprint_end_date: date
    story_points_closed: int
    tasks_completed: int
    deadlines_missed: int
    average_task_completion_time: float  # in hours
    activity_analysis: str | None
    recommendations: List[Recommendation] | None = []

class SprintReportRequest(BaseModel):
    user_id: int
    sprint_id: int 
