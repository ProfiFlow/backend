from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models.report import SprintReportDB
from app.database.models.team_report import TeamSprintReportDB

class ReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_or_update_sprint_report(self, **kwargs):
        obj = await self.session.execute(
            select(SprintReportDB).where(
                SprintReportDB.user_id == kwargs['user_id'],
                SprintReportDB.tracker_id == kwargs['tracker_id'],
                SprintReportDB.sprint_id == kwargs['sprint_id']
            )
        )
        report = obj.scalar_one_or_none()
        if not report:
            report = SprintReportDB(
                user_id=kwargs['user_id'],
                tracker_id=kwargs['tracker_id'],
                sprint_id=kwargs['sprint_id'],
                sprint_name=kwargs['sprint_name'],
                sprint_start_date=kwargs['sprint_start_date'],
                sprint_end_date=kwargs['sprint_end_date'],
                story_points_closed=kwargs['story_points_closed'].current,
                tasks_completed=kwargs['tasks_completed'].current,
                deadlines_missed=kwargs['deadlines_missed'].current,
                average_task_completion_time=kwargs['average_task_completion_time'].current,
                activity_analysis=kwargs['activity_analysis'],
                recommendations=[r.model_dump() for r in (kwargs['recommendations'] or [])],
            )
            self.session.add(report)
        else:
            report.story_points_closed = kwargs['story_points_closed'].current
            report.tasks_completed = kwargs['tasks_completed'].current
            report.deadlines_missed = kwargs['deadlines_missed'].current
            report.average_task_completion_time = kwargs['average_task_completion_time'].current
            report.activity_analysis = kwargs['activity_analysis']
            report.recommendations = [r.model_dump() for r in (kwargs['recommendations'] or [])]
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def get_previous_sprint_report(self, user_id: int, tracker_id: int, sprint_start_date):
        q = await self.session.execute(
            select(SprintReportDB)
            .where(SprintReportDB.user_id == user_id)
            .where(SprintReportDB.tracker_id == tracker_id)
            .where(SprintReportDB.sprint_start_date < sprint_start_date)
            .order_by(SprintReportDB.sprint_start_date.desc())
        )
        return q.scalars().first()

    async def get_sprint_report_by_id(self, user_id: int, tracker_id: int, sprint_id: int):
        q = await self.session.execute(
            select(SprintReportDB)
            .where(SprintReportDB.user_id == user_id)
            .where(SprintReportDB.tracker_id == tracker_id)
            .where(SprintReportDB.sprint_id == sprint_id)
        )
        return q.scalars().first()

class TeamReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_team_sprint_report_by_id(self, tracker_id: int, sprint_id: int):
        q = await self.session.execute(
            select(TeamSprintReportDB)
            .where(TeamSprintReportDB.tracker_id == tracker_id)
            .where(TeamSprintReportDB.sprint_id == sprint_id)
        )
        return q.scalars().first()

    async def save_or_update_team_sprint_report(self, tracker_id: int, sprint_id: int, sprint_start_date, sprint_end_date, employee_stats):
        obj = await self.session.execute(
            select(TeamSprintReportDB)
            .where(TeamSprintReportDB.tracker_id == tracker_id)
            .where(TeamSprintReportDB.sprint_id == sprint_id)
        )
        report = obj.scalar_one_or_none()
        if not report:
            report = TeamSprintReportDB(
                tracker_id=tracker_id,
                sprint_id=sprint_id,
                sprint_start_date=sprint_start_date,
                sprint_end_date=sprint_end_date,
                employee_stats=employee_stats,
            )
            self.session.add(report)
        else:
            report.sprint_start_date = sprint_start_date
            report.sprint_end_date = sprint_end_date
            report.employee_stats = employee_stats
        await self.session.commit()
        await self.session.refresh(report)
        return report 
