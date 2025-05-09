from pydantic import BaseModel
from typing import List, Optional

# Модель для данных задачи (упрощенная версия)
class Task(BaseModel):
    key: str
    summary: str
    statusType: dict
    assignee: Optional[dict] = None
    resolvedAt: Optional[str] = None
    createdAt: str
    updatedAt: str
    sprint: Optional[List[dict]] = None

# Модель для входящего запроса (список задач)
class TrackerData(BaseModel):
    tasks: List[Task]