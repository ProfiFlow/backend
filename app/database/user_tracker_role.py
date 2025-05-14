import enum

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from . import Base


class RoleEnum(enum.Enum):
    manager = "manager"
    employee = "employee"


class UserTrackerRole(Base):
    __tablename__ = "user_tracker_roles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    tracker_id = Column(Integer, ForeignKey("trackers.id"), primary_key=True)
    role = Column(Enum(RoleEnum), nullable=False)
    is_current = Column(Boolean, nullable=False, default=False, server_default="false")

    user = relationship("User", back_populates="tracker_associations")
    tracker = relationship("Tracker", back_populates="user_associations")
