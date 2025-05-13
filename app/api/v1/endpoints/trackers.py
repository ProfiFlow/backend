from typing import List

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserId, TrackerRepo, UserRepo
from app.schemas.tracker import TrackerCreate, TrackerResponse

router = APIRouter()


@router.get(
    "",
    response_model=List[TrackerResponse],
    summary="Получить список всех трекеров",
    response_description="Список трекеров с информацией о ролях пользователя",
    responses={
        200: {"description": "Список трекеров успешно получен"},
        500: {"description": "Ошибка сервера"},
    },
)
async def get_trackers(
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
    tracker_repo: TrackerRepo,
):
    """
    Получает список всех доступных трекеров с информацией о ролях текущего пользователя.

    Функция извлекает все трекеры из базы данных и добавляет к каждому из них
    информацию о роли текущего пользователя в этом трекере, если таковая имеется.

    Возвращает:
    - Список всех трекеров с информацией о роли пользователя для каждого трекера
    """
    # Get all trackers
    trackers = await tracker_repo.get_all()

    # Prepare response with roles
    tracker_responses = []
    for tracker in trackers:
        response = TrackerResponse.model_validate(tracker)
        # Get role for this tracker if exists
        role = await user_repo.get_user_role_for_tracker(current_user_id, tracker.id)
        response.role = role
        tracker_responses.append(response)

    return tracker_responses


@router.post(
    "",
    response_model=TrackerResponse,
    summary="Создать новый трекер",
    response_description="Информация о созданном трекере",
    responses={
        200: {"description": "Трекер успешно создан"},
        400: {"description": "Отсутствуют необходимые идентификаторы"},
        500: {"description": "Ошибка сервера"},
    },
)
async def create_tracker(
    tracker: TrackerCreate,
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
    tracker_repo: TrackerRepo,
):
    """
    Создает новый трекер и назначает создателя менеджером этого трекера.

    Функция создает новый трекер в системе на основе предоставленных данных
    (имя, cloud_id, org_id) и автоматически назначает пользователя, создавшего
    трекер, менеджером этого трекера. Также этот трекер становится текущим
    для создавшего его пользователя.

    Параметры:
    - tracker: Данные для создания трекера (имя, cloud_id, org_id)

    Возвращает:
    - Информацию о созданном трекере
    """
    # Check that at least one identifier is provided
    if not tracker.yandex_cloud_id and not tracker.yandex_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of cloud_id or org_id must be provided",
        )

    new_tracker = await tracker_repo.create_or_update_yandex_tracker(
        name=tracker.name,
        cloud_id=tracker.yandex_cloud_id,
        org_id=tracker.yandex_org_id,
    )

    # Set the creator as manager and this tracker as their current one
    await user_repo.set_current_tracker(
        user_id=current_user_id,
        tracker_id=new_tracker.id,
        role="manager",  # Set role to manager
    )
    return new_tracker


@router.get(
    "/current",
    response_model=TrackerResponse,
    summary="Получить текущий трекер пользователя",
    response_description="Информация о текущем активном трекере",
    responses={
        200: {"description": "Текущий трекер успешно получен"},
        404: {"description": "Текущий трекер не найден"},
        500: {"description": "Ошибка сервера"},
    },
)
async def get_current_tracker(
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
):
    """
    Получает текущий активный трекер пользователя.

    Функция извлекает информацию о текущем выбранном трекере пользователя,
    включая роль пользователя в этом трекере. Если у пользователя не установлен
    текущий трекер, возвращается ошибка 404.

    Возвращает:
    - Информацию о текущем активном трекере пользователя с указанием роли
    """
    result = await user_repo.get_user_current_tracker(current_user_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active tracker set for this user",
        )

    active_tracker, role = result
    response = TrackerResponse.model_validate(active_tracker)
    response.role = role

    return response


@router.put(
    "/current/{tracker_id}",
    summary="Установить текущий трекер для пользователя",
    response_description="Статус установки текущего трекера",
    responses={
        200: {"description": "Трекер успешно установлен как текущий"},
        404: {"description": "Трекер не найден"},
        500: {"description": "Ошибка сервера"},
    },
)
async def set_current_tracker(
    tracker_id: int,
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
    tracker_repo: TrackerRepo,
):
    """
    Устанавливает указанный трекер как текущий для пользователя.

    Функция устанавливает указанный трекер как текущий активный для пользователя.
    Если пользователь еще не имеет роли в этом трекере, ему будет назначена
    роль "employee" по умолчанию.

    Параметры:
    - tracker_id: ID трекера, который нужно установить как текущий

    Возвращает:
    - Объект с сообщением об успешной установке трекера и информацией о трекере
    """
    tracker_db = await tracker_repo.get_by_id(tracker_id)
    if not tracker_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tracker not found"
        )

    await user_repo.set_current_tracker(
        user_id=current_user_id,
        tracker_id=tracker_db.id,
    )

    # Get the role for this tracker
    role = await user_repo.get_user_role_for_tracker(current_user_id, tracker_db.id)

    # Create response with role information
    tracker_response = TrackerResponse.model_validate(tracker_db)
    tracker_response.role = role

    return {
        "message": "Tracker successfully set as current",
        "tracker": tracker_response,
    }


@router.get(
    "/{tracker_id}",
    response_model=TrackerResponse,
    summary="Получить трекер по ID",
    response_description="Информация о трекере с ролью пользователя",
    responses={
        200: {"description": "Информация о трекере успешно получена"},
        404: {"description": "Трекер не найден"},
        500: {"description": "Ошибка сервера"},
    },
)
async def get_tracker(
    tracker_id: int,
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
    tracker_repo: TrackerRepo,
):
    """
    Получает информацию о трекере по его ID.

    Функция извлекает данные о трекере с указанным ID и добавляет
    информацию о роли текущего пользователя в этом трекере.

    Параметры:
    - tracker_id: ID трекера для получения информации

    Возвращает:
    - Информацию о трекере с ролью пользователя в нем
    """
    # Get the tracker
    tracker = await tracker_repo.get_by_id(tracker_id)
    if not tracker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tracker not found"
        )

    # Get the user's role for this tracker
    response = TrackerResponse.model_validate(tracker)
    role = await user_repo.get_user_role_for_tracker(current_user_id, tracker_id)
    response.role = role

    return response
