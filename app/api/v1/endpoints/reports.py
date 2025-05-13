import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserId, ReportSvc, TrackerSvc, UserRepo
from app.schemas.sprint_report import SprintReport, SprintReportRequest
from app.schemas.team_report import TeamSprintReport, TeamSprintReportRequest
from app.schemas.yandex_tracker import Sprint

log = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=SprintReport,
    summary="Создать отчет по спринту для сотрудника",
    response_description="Детальный отчет по спринту",
    responses={
        200: {"description": "Отчет успешно сгенерирован"},
        404: {"description": "Спринт или пользователь не найден"},
        500: {"description": "Ошибка сервера"},
        503: {"description": "Сервис ML недоступен"},
    },
)
async def generate_sprint_report(
    request: SprintReportRequest,
    reports: ReportSvc,
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
):
    """
    Генерирует детальный отчет по спринту для текущего пользователя.

    Функция создает отчет по работе пользователя в указанном спринте.
    Обращается к сервису ML для анализа активности и формирования рекомендаций.

    Параметры:
    - request: Объект запроса с ID спринта для генерации отчета

    Возвращает:
    - Детальный отчет по спринту с анализом активности пользователя

    Исключения:
    - 404: Если спринт или пользователь не найдены
    - 503: Если сервис ML недоступен
    - 500: При внутренних ошибках сервера
    """
    try:
        user = await user_repo.get_by_id(current_user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        report = await reports.generate_sprint_report(
            user=user,
            sprint_id=request.sprint_id,
            current_user_id=current_user_id,
        )
        return report
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ML Service unavailable: {e}",
        )
    except Exception as e:
        log.error(f"Error generating sprint report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating report: {str(e)}",
        )


@router.post(
    "/team",
    response_model=TeamSprintReport,
    summary="Создать командный отчет по спринту",
    response_description="Детальный отчет по спринту для всей команды",
    responses={
        200: {"description": "Командный отчет успешно сгенерирован"},
        403: {"description": "Недостаточно прав для создания командного отчета"},
        500: {"description": "Ошибка сервера"},
        503: {"description": "Сервис ML недоступен"},
    },
)
async def generate_team_sprint_report(
    request: TeamSprintReportRequest,
    reports: ReportSvc,
    current_user_id: CurrentUserId,
) -> TeamSprintReport:
    """
    Генерирует командный отчет по спринту для всех участников команды.

    Функция создает агрегированный отчет по работе всей команды в указанном спринте.
    Для выполнения операции требуется роль менеджера.

    Параметры:
    - request: Объект запроса с ID спринта для генерации командного отчета

    Возвращает:
    - Командный отчет по спринту с анализом активности всех участников

    Исключения:
    - 403: Если у пользователя недостаточно прав (не менеджер)
    - 503: Если сервис ML недоступен
    - 500: При внутренних ошибках сервера
    """
    try:
        report = await reports.generate_team_sprint_report(
            current_user_id=current_user_id,
            sprint_id=request.sprint_id,
        )
        return report
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ML Service unavailable: {e}",
        )
    except Exception as e:
        log.error(f"Error generating team sprint report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate team report",
        )


@router.get(
    "/sprints",
    response_model=list[Sprint],
    summary="Получить список спринтов текущего трекера",
    response_description="Список спринтов",
    responses={
        200: {"description": "Список спринтов успешно получен"},
        400: {"description": "Пользователь не привязан к трекеру"},
        500: {"description": "Ошибка сервера"},
    },
)
async def get_sprints_for_current_tracker(
    tracker_service: TrackerSvc,
    user_repo: UserRepo,
    current_user_id: CurrentUserId,
):
    """
    Получает список всех спринтов для текущего трекера пользователя.

    Функция извлекает список спринтов из текущего активного трекера пользователя.
    Для работы функции пользователь должен иметь установленный текущий трекер.

    Возвращает:
    - Список всех спринтов текущего трекера

    Исключения:
    - 400: Если у пользователя не установлен текущий трекер
    - 500: При внутренних ошибках сервера
    """
    tracker_info = await user_repo.get_user_current_tracker(current_user_id)
    if not tracker_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь не привязан к трекеру",
        )

    sprints = await tracker_service.get_sprints(current_user_id)
    return sprints
