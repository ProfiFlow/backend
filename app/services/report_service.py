from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.user import UserRepository
from app.database.user import User
from app.schemas.report import SprintStats
from app.schemas.sprint_report import SprintReport
from app.schemas.yandex_tracker import Task
from app.schemas.team_report import EmployeeSprintStats, TeamSprintReport, MetricWithComparison
from app.schemas.yandex_tracker import Sprint as SprintSchema
from app.database.repositories.report import ReportRepository, TeamReportRepository
import logging

from app.services.yandex_gpt_service import YandexGPTMLService
from app.services.yandex_tracker import YandexTrackerService

log = logging.getLogger(__name__)


class ReportService:
    """
    Service for generating various types of reports.
    Relies on injected tracker and ML services.
    """
    def __init__(self, db: AsyncSession, 
                yandex_tracker_service: YandexTrackerService, 
                yandex_gpt_service: YandexGPTMLService,
                user_repo: UserRepository,
                report_repo: ReportRepository,
                team_report_repo: TeamReportRepository,
            ):
        self.db = db
        self.yandex_tracker_service = yandex_tracker_service
        self.yandex_gpt_service = yandex_gpt_service
        self.user_repo = user_repo
        self.report_repo = report_repo
        self.team_report_repo = team_report_repo

    
    async def generate_sprint_report(
        self,
        user: User,
        sprint_id: int,
        current_user_id: int,
    ) -> SprintReport:
        """
        Generate a comprehensive sprint report for an employee.
        Uses provided service instances.
        """

        sprint = await self.yandex_tracker_service.get_sprint(sprint_id, current_user_id)
        if not sprint:
            raise ValueError(f"Sprint with ID {sprint_id} not found.")

        # Получаем tracker_id через репозиторий
        tracker_info = await self.user_repo.get_user_current_tracker(user.id)
        if not tracker_info:
            raise ValueError("Не удалось определить tracker_id для пользователя")
        tracker, _ = tracker_info
        tracker_id = tracker.id

        tasks = await self.yandex_tracker_service.get_sprint_tasks(sprint_id, current_user_id, user.login)
        sprint_stats = await self._process_tasks(tasks, current_user_id)

        # Проверяем, есть ли уже отчет по этому спринту
        existing_report = await self.report_repo.get_sprint_report_by_id(user.id, tracker_id, sprint_id)
        if existing_report:
            # Получаем предыдущий отчет для сравнения
            prev_report = await self.report_repo.get_previous_sprint_report(user.id, tracker_id, existing_report.sprint_start_date)
            prev_stats = None
            if prev_report:
                prev_stats = SprintStats(
                    total_story_points=prev_report.story_points_closed,
                    total_tasks=prev_report.tasks_completed,
                    deadlines_missed=prev_report.deadlines_missed,
                    average_completion_time=prev_report.average_task_completion_time,
                )
            return SprintReport(
                user_id=existing_report.user_id,
                employee_name=user.display_name,
                sprint_name=existing_report.sprint_name,
                sprint_start_date=existing_report.sprint_start_date,
                sprint_end_date=existing_report.sprint_end_date,
                story_points_closed=self._create_metric_comparison(
                    existing_report.story_points_closed, prev_stats.total_story_points if prev_stats else None
                ),
                tasks_completed=self._create_metric_comparison(
                    existing_report.tasks_completed, prev_stats.total_tasks if prev_stats else None
                ),
                deadlines_missed=self._create_metric_comparison(
                    existing_report.deadlines_missed, prev_stats.deadlines_missed if prev_stats else None
                ),
                average_task_completion_time=self._create_metric_comparison(
                    existing_report.average_task_completion_time, prev_stats.average_completion_time if prev_stats else None
                ),
                activity_analysis=existing_report.activity_analysis,
                recommendations=existing_report.recommendations,
            )

        # --- Получение предыдущего отчета из БД ---
        prev_report = await self.report_repo.get_previous_sprint_report(user.id, tracker_id, sprint.start_date)
        prev_stats = None
        if prev_report:
            prev_stats = SprintStats(
                total_story_points=prev_report.story_points_closed,
                total_tasks=prev_report.tasks_completed,
                deadlines_missed=prev_report.deadlines_missed,
                average_completion_time=prev_report.average_task_completion_time,
            )
        # --- Формируем сравнения метрик ---
        story_points_closed = self._create_metric_comparison(
            sprint_stats.total_story_points, prev_stats.total_story_points if prev_stats else None
        )
        tasks_completed = self._create_metric_comparison(
            sprint_stats.total_tasks, prev_stats.total_tasks if prev_stats else None
        )
        deadlines_missed = self._create_metric_comparison(
            sprint_stats.deadlines_missed, prev_stats.deadlines_missed if prev_stats else None
        )
        average_task_completion_time = self._create_metric_comparison(
            sprint_stats.average_completion_time, prev_stats.average_completion_time if prev_stats else None
        )

        try:
            activity_analysis = await self.yandex_gpt_service.analyze_employee_activity(tasks, sprint_stats)
            recommendations = await self.yandex_gpt_service.generate_employee_recommendations(tasks, sprint_stats)
        except Exception as e:
            log.error(f"LLM error: {e}")
            raise

        # Сохраняем и возвращаем отчет только если оба результата получены
        await self.report_repo.save_or_update_sprint_report(
            user_id=user.id,
            tracker_id=tracker_id,
            sprint_id=sprint_id,
            sprint_name=sprint.name,
            sprint_start_date=sprint.start_date,
            sprint_end_date=sprint.end_date,
            story_points_closed=story_points_closed,
            tasks_completed=tasks_completed,
            deadlines_missed=deadlines_missed,
            average_task_completion_time=average_task_completion_time,
            activity_analysis=activity_analysis,
            recommendations=recommendations,
        )
        return SprintReport(
            user_id=user.id,
            employee_name=user.display_name,
            sprint_name=sprint.name,
            sprint_start_date=sprint.start_date,
            sprint_end_date=sprint.end_date,
            story_points_closed=story_points_closed,
            tasks_completed=tasks_completed,
            deadlines_missed=deadlines_missed,
            average_task_completion_time=average_task_completion_time,
            activity_analysis=activity_analysis,
            recommendations=recommendations,
        )

    def _calculate_percent_change(self, current: float, previous: float) -> float:
        """
        Calculate percent change between current and previous values.
        Positive percentage means improvement, negative means decline.
        """
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        
        return ((current - previous) / previous) * 100
    
    def _create_metric_comparison(self, current: float, previous: Optional[float] = None) -> MetricWithComparison:
        """
        Create a metric with comparison between current and previous sprint.
        """
        metric = MetricWithComparison(current=current)
        
        if previous is not None:
            metric.previous = previous
            metric.change_percent = self._calculate_percent_change(current, previous)
            
        return metric
    
    async def   generate_team_sprint_report(
        self,
        current_user_id: int,
        sprint_id: int,
    ) -> TeamSprintReport:
        """
        Generate a comprehensive sprint report for the entire team.
        Uses provided service instances.
        """

        # Получаем текущий трекер пользователя
        tracker_info = await self.user_repo.get_user_current_tracker(current_user_id)
        if not tracker_info:
            raise ValueError("Не удалось определить tracker_id для пользователя")
        tracker, role = tracker_info

        if role != "manager":
            raise ValueError("У вас нет доступа к генерации командных отчетов")

        tracker_id = tracker.id

        # --- Проверка наличия отчёта в БД ---
        existing_team_report = await self.team_report_repo.get_team_sprint_report_by_id(tracker_id, sprint_id)
        if existing_team_report:
            employee_stats_final = [
                EmployeeSprintStats(**emp) for emp in existing_team_report.employee_stats
            ]
            return TeamSprintReport(
                sprint_id=existing_team_report.sprint_id,
                sprint_start_date=existing_team_report.sprint_start_date,
                sprint_end_date=existing_team_report.sprint_end_date,
                employee_stats=employee_stats_final,
            )

        # Получаем всех пользователей, привязанных к этому трекеру
        users = await self.user_repo.get_users_for_tracker(tracker_id)

        # Получаем инфо о спринте
        sprint = await self.yandex_tracker_service.get_sprint(sprint_id, current_user_id)
        if not sprint:
            raise ValueError(f"Sprint with ID {sprint_id} not found.")

        # Получаем предыдущий спринт (по дате)
        prev_sprint = None
        all_sprints = await self.yandex_tracker_service.get_sprints(current_user_id)
        sprints_objs = [SprintSchema(**s) for s in all_sprints]
        sprints_sorted = sorted(sprints_objs, key=lambda s: s.start_date)
        for idx, s in enumerate(sprints_sorted):
            if s.id == sprint_id and idx > 0:
                prev_sprint = sprints_sorted[idx-1]
                break

        # Собираем employee_stats для текущего и предыдущего спринта
        employee_stats = []
        prev_employee_stats = []
        for user in users:
            # --- Переиспользуем generate_sprint_report для каждого пользователя ---
            sprint_report = await self.generate_sprint_report(user, sprint_id, current_user_id)
            # Метрики с сравнением (будут использоваться ниже)
            story_points_closed = sprint_report.story_points_closed
            tasks_completed = sprint_report.tasks_completed
            deadlines_missed = sprint_report.deadlines_missed
            average_task_completion_time = sprint_report.average_task_completion_time
            employee_stats.append({
                "employee_id": str(user.id),
                "employee_name": user.display_name,
                "story_points_closed": story_points_closed.model_dump(),
                "tasks_completed": tasks_completed.model_dump(),
                "deadlines_missed": deadlines_missed.model_dump(),
                "average_task_completion_time": average_task_completion_time.model_dump(),
            })

            log.debug(f"Employee stats: {employee_stats}")
            # Метрики за предыдущий спринт — только из БД
            prev_stats_report = None
            if prev_sprint:
                prev_stats_report = await self.report_repo.get_sprint_report_by_id(user.id, tracker_id, prev_sprint.id)
            if prev_stats_report:
                prev_employee_stats.append({
                    "employee_id": str(user.id),
                    "employee_name": user.display_name,
                    "story_points_closed": {"current": prev_stats_report.story_points_closed},
                    "tasks_completed": {"current": prev_stats_report.tasks_completed},
                    "deadlines_missed": {"current": prev_stats_report.deadlines_missed},
                    "average_task_completion_time": {"current": prev_stats_report.average_task_completion_time},
                })

        # Отправляем employee_stats и prev_employee_stats в LLM для анализа и рейтинга
        try:
            
            llm_result = await self.yandex_gpt_service.rate_team_performance(
                current_user_id=current_user_id,
                employee_stats=employee_stats,
                prev_employee_stats=prev_employee_stats if prev_employee_stats else None
            )
            log.debug(f"LLM result: {llm_result}")
            # llm_result: List[dict] с rating и rating_explanation для каждого employee_id
            rating_map = {str(r["employee_id"]): r for r in llm_result}
        except Exception as e:
            log.error(f"LLM error (team report): {e}")
            raise e

        # Формируем финальный список EmployeeSprintStats
        employee_stats_final = []
        for emp in employee_stats:
            log.debug(f"Employee stats: {emp}")
            log.debug(f"Rating map: {rating_map}")
            rid = emp["employee_id"]
            rating = rating_map.get(rid, {}).get("rating", 3)
            rating_explanation = rating_map.get(rid, {}).get("rating_explanation", "Ошибка AI при оценке производительности")
            employee_stats_final.append(EmployeeSprintStats(
                employee_id=emp["employee_id"],
                employee_name=emp["employee_name"],
                story_points_closed=MetricWithComparison(**emp["story_points_closed"]),
                tasks_completed=MetricWithComparison(**emp["tasks_completed"]),
                deadlines_missed=MetricWithComparison(**emp["deadlines_missed"]),
                average_task_completion_time=MetricWithComparison(**emp["average_task_completion_time"]),
                rating=rating,
                rating_explanation=rating_explanation,
            ))

        # Сохраняем отчет
        await self.team_report_repo.save_or_update_team_sprint_report(
            tracker_id=tracker_id,
            sprint_id=sprint_id,
            sprint_start_date=sprint.start_date,
            sprint_end_date=sprint.end_date,
            employee_stats=[emp.model_dump() for emp in employee_stats_final],
        )
        return TeamSprintReport(
            sprint_id=sprint_id,
            sprint_start_date=sprint.start_date,
            sprint_end_date=sprint.end_date,
            employee_stats=employee_stats_final,
        )

    async def _process_tasks(self, tasks: List[Task], current_user_id: int) -> SprintStats:
        """
        Process tasks to extract relevant statistics.
        """
        total_story_points = 0
        total_tasks = 0
        deadlines_missed = 0
        total_completion_time = 0.0
        
        for task in tasks:
            total_story_points += task.story_points if task.story_points else 0
            total_tasks += 1
            
            if task.deadline and (task.status.key == "done" and task.deadline < task.resolved_at or task.deadline < datetime.utcnow().date()):
                deadlines_missed += 1
            
            if task.status.key == "done":
                total_completion_time += await self.yandex_tracker_service.get_issue_logged_time(
                    task.id, current_user_id
                )
        
        return SprintStats(
            total_story_points=total_story_points,
            total_tasks=total_tasks,
            deadlines_missed=deadlines_missed,
            average_completion_time=total_completion_time / total_tasks if total_tasks > 0 else 0
        )
