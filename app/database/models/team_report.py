from sqlalchemy import JSON, Column, Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class TeamSprintReportDB(Base):
    __tablename__ = "team_sprint_reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tracker_id = Column(Integer, ForeignKey("trackers.id"), nullable=False)
    sprint_id = Column(Integer, nullable=False)
    sprint_start_date = Column(Date, nullable=False)
    sprint_end_date = Column(Date, nullable=False)
    employee_stats = Column(
        JSON, nullable=False
    )  # Список EmployeeSprintStats в виде JSON
    __table_args__ = (
        UniqueConstraint("tracker_id", "sprint_id", name="_tracker_sprint_uc"),
    )
    tracker = relationship("Tracker")
