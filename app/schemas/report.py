from pydantic import BaseModel


class SprintStats(BaseModel):
    total_story_points: int
    total_tasks: int
    deadlines_missed: int
    average_completion_time: float
