from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from . import Base


class Tracker(Base):
    __tablename__ = "trackers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    tracker_type = Column(
        String(50), nullable=False, default="yandex"
    )  # For future support of other tracker types

    # Yandex-specific fields
    yandex_cloud_id = Column(String(50), nullable=True)
    yandex_org_id = Column(String(50), nullable=True)

    # Technical fields
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    # Relationship with users
    user_associations = relationship(
        "UserTrackerRole", back_populates="tracker"
    )  # Added

    def __repr__(self):
        return f"<Tracker(id={self.id}, name={self.name}, type={self.tracker_type})>"
