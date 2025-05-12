from pydantic import BaseModel


class SprintStats(BaseModel):
    total_story_points: float
    total_tasks: float
    deadlines_missed: float
    average_completion_time: float
