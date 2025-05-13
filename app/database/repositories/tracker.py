from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..tracker import Tracker


class TrackerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, tracker_id: int) -> Tracker | None:
        """Get tracker by ID"""
        result = await self.session.execute(
            select(Tracker).where(Tracker.id == tracker_id)
        )
        return result.scalar_one_or_none()

    async def get_by_cloud_id(self, cloud_id: str) -> Tracker | None:
        """Get tracker by Yandex Cloud ID"""
        result = await self.session.execute(
            select(Tracker).where(Tracker.yandex_cloud_id == cloud_id)
        )
        return result.scalar_one_or_none()

    async def get_by_org_id(self, org_id: str) -> Tracker | None:
        """Get tracker by Yandex Organization ID"""
        result = await self.session.execute(
            select(Tracker).where(Tracker.yandex_org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> list[Tracker]:
        """Get all trackers"""
        result = await self.session.execute(select(Tracker).where(Tracker.is_active))
        return result.scalars().all()

    async def create_or_update_yandex_tracker(
        self,
        name: str,
        cloud_id: str = None,
        org_id: str = None,
    ) -> Tracker:
        """Create or update Yandex tracker"""
        tracker = None

        # Try to find by cloud_id or org_id
        if cloud_id:
            tracker = await self.get_by_cloud_id(cloud_id)
        elif org_id:
            tracker = await self.get_by_org_id(org_id)

        if not tracker:
            # Create new tracker
            tracker = Tracker(
                name=name,
                tracker_type="yandex",
                yandex_cloud_id=cloud_id,
                yandex_org_id=org_id,
                created_at=datetime.utcnow(),
            )
            self.session.add(tracker)
        else:
            # Update existing
            tracker.name = name
            tracker.yandex_cloud_id = cloud_id or tracker.yandex_cloud_id
            tracker.yandex_org_id = org_id or tracker.yandex_org_id
            tracker.updated_at = datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(tracker)
        return tracker
