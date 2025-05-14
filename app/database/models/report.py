from sqlalchemy import (
    JSON,
    Column,
    Date,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class SprintReportDB(Base):
    __tablename__ = "sprint_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    tracker_id = Column(Integer, nullable=False)
    sprint_id = Column(Integer, nullable=False)
    sprint_name = Column(String, nullable=False)
    sprint_start_date = Column(Date, nullable=False)
    sprint_end_date = Column(Date, nullable=False)
    story_points_closed = Column(Float, nullable=False)
    tasks_completed = Column(Integer, nullable=False)
    deadlines_missed = Column(Integer, nullable=False)
    average_task_completion_time = Column(Float, nullable=False)
    activity_analysis = Column(String, nullable=True)
    recommendations = Column(JSON, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "tracker_id"],
            ["user_tracker_roles.user_id", "user_tracker_roles.tracker_id"],
        ),
        Index("ix_sprint_report_user_tracker", "user_id", "tracker_id"),
    )

    user_tracker_role = relationship("UserTrackerRole")
