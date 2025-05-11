from datetime import date, datetime
from multiprocessing import process
from time import timezone
from typing import Optional, Dict, List, Any, Type
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.user import UserRepository
from app.database.user import User
from app.schemas.sprint_report import SprintReport
from app.schemas.yandex_tracker import Task
from app.schemas.team_report import TeamSprintReport, EmployeeSprintStats, MetricWithComparison
from app.services.yandex_tracker import YandexTrackerService
import logging

log = logging.getLogger(__name__)


class ReportService:
    """
    Service for generating various types of reports.
    Relies on injected tracker and ML services.
    """
    
    async def generate_sprint_report(
        self,
        db: AsyncSession,
        current_user_id: int,
        user: User,
        sprint_id: int,
    ) -> SprintReport:
        """
        Generate a comprehensive sprint report for an employee.
        Uses provided service instances.
        """
        # Get employee information
        yandex_tracker_service = YandexTrackerService(db)

        sprint = await yandex_tracker_service.get_sprint(sprint_id, current_user_id)
        if not sprint:
            raise ValueError(f"Sprint with ID {sprint_id} not found.")

        tasks = await yandex_tracker_service.get_sprint_tasks(sprint_id, current_user_id, user.login)

        sprint_stats = await self._process_tasks(tasks, yandex_tracker_service)
        
        activity_analysis = None
        
        recommendations = None
        
        return SprintReport(
            user_id=user.id,
            employee_name=user.display_name,
            sprint_name=sprint.name,
            sprint_start_date=sprint.start_date,
            sprint_end_date=sprint.end_date,
            story_points_closed=sprint_stats["total_story_points"],
            tasks_completed=sprint_stats["total_tasks"],
            deadlines_missed=sprint_stats["deadlines_missed"],
            average_task_completion_time=sprint_stats["average_completion_time"],
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
    
    # async def generate_team_sprint_report(
    #     self, 
    #     sprint_number: int, 
    # ) -> TeamSprintReport:
    #     """
    #     Generate a comprehensive sprint report for the entire team.
    #     Uses provided service instances.
    #     """
    #     # Get sprint information
    #     sprint_info = tracker_service.get_sprint_info(sprint_number)
        
    #     # Get team statistics for the sprint
    #     team_stats = tracker_service.get_team_sprint_statistics(sprint_number)
        
    #     # Collect tasks by employee for analysis
    #     tasks_by_employee = {}
    #     for employee_stat in team_stats["employee_stats"]:
    #         employee_id = employee_stat["employee_id"]
    #         # Avoid calling get_employee_tasks again if stats already contain tasks?
    #         # Assuming get_team_sprint_statistics doesn't return tasks per employee.
    #         tasks = tracker_service.get_employee_tasks(employee_id, sprint_number)
    #         tasks_by_employee[employee_id] = tasks
        
    #     # Generate team activity analysis
    #     activity_analysis = ml_service.analyze_team_activity(tasks_by_employee)
        
    #     # Generate recommendations for the team
    #     recommendations = ml_service.generate_team_recommendations(team_stats)
        
    #     # Format employee stats for the report, including performance rating
    #     employee_stats = []
    #     for emp_stat in team_stats["employee_stats"]:
    #         employee_id = emp_stat["employee_id"]
    #         current_stats = emp_stat["stats"]
    #         # Retrieve tasks for this specific employee for rating context
    #         employee_tasks = tasks_by_employee.get(employee_id, []) 
            
    #         # Get previous sprint statistics for comparison
    #         previous_stats = tracker_service.get_previous_sprint_statistics(employee_id, sprint_number)
            
    #         # Get employee performance rating, passing tasks as context
    #         performance = ml_service.rate_employee_performance(
    #             employee_id=employee_id, 
    #             sprint_stats=current_stats, 
    #             tasks=employee_tasks,  # Pass tasks here
    #             previous_sprint_stats=previous_stats
    #         )
            
    #         # Create metrics with comparison
    #         story_points = self._create_metric_comparison(
    #             current=current_stats["story_points_closed"],
    #             previous=previous_stats["story_points_closed"] if previous_stats else None
    #         )
            
    #         tasks_completed = self._create_metric_comparison(
    #             current=current_stats["tasks_completed"],
    #             previous=previous_stats["tasks_completed"] if previous_stats else None
    #         )
            
    #         deadlines_missed = self._create_metric_comparison(
    #             current=current_stats["deadlines_missed"],
    #             previous=previous_stats["deadlines_missed"] if previous_stats else None
    #         )
            
    #         avg_completion_time = self._create_metric_comparison(
    #             current=current_stats["average_task_completion_time"],
    #             previous=previous_stats["average_task_completion_time"] if previous_stats else None
    #         )
            
    #         # Create employee stats object
    #         employee_stats.append(
    #             EmployeeSprintStats(
    #                 employee_id=emp_stat["employee_id"],
    #                 employee_name=emp_stat["employee_name"],
    #                 story_points_closed=story_points,
    #                 tasks_completed=tasks_completed,
    #                 deadlines_missed=deadlines_missed,
    #                 average_task_completion_time=avg_completion_time,
    #                 rating=performance["rating"],
    #                 rating_explanation=performance["explanation"]
    #             )
    #         )
        
    #     # Sort employee stats by rating (best to worst)
    #     employee_stats.sort(key=lambda x: x.rating, reverse=True)
        
    #     # Create and return the team report
    #     return TeamSprintReport(
    #         sprint_number=sprint_number,
    #         sprint_start_date=sprint_info["start_date"],
    #         sprint_end_date=sprint_info["end_date"],
    #         total_story_points_closed=team_stats["total_story_points_closed"],
    #         total_tasks_completed=team_stats["total_tasks_completed"],
    #         total_deadlines_missed=team_stats["total_deadlines_missed"],
    #         avg_task_completion_time=team_stats["avg_task_completion_time"],
    #         activity_analysis=activity_analysis,
    #         recommendations=recommendations,
    #         employee_stats=employee_stats
    #     ) 

    async def _process_tasks(self, tasks: List[Task], yandex_tracker_service: YandexTrackerService) -> Dict[str, Any]:
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
                total_completion_time += await yandex_tracker_service.get_issue_logged_time(
                    task.id
                )
        
        return {
            "total_story_points": total_story_points,
            "total_tasks": total_tasks,
            "deadlines_missed": deadlines_missed,
            "average_completion_time": total_completion_time / total_tasks if total_tasks > 0 else 0
        }
