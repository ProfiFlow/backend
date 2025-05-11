import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.tracker import TrackerRepository
from app.database.repositories.user import UserRepository
from app.database.user import User

log = logging.getLogger(__name__)


class TrackerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tracker_repo = TrackerRepository(session)
        self.user_repo = UserRepository(session)
