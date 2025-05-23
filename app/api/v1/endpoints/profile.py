from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserId, UserRepo
from app.schemas.tracker import TrackerResponse
from app.schemas.user import UserResponse

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Получить профиль текущего пользователя",
    response_description="Информация о профиле пользователя и связанных трекерах",
    responses={
        200: {"description": "Профиль пользователя успешно получен"},
        404: {"description": "Пользователь не найден"},
        500: {"description": "Ошибка сервера"},
    },
)
async def get_my_profile(
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
):
    """
    Получает профиль текущего авторизованного пользователя со всей информацией.

    Функция извлекает полную информацию о текущем пользователе, включая:
    - Основные данные пользователя (ID, логин, email, имя и т.д.)
    - Список всех трекеров, к которым имеет доступ пользователь, вместе с ролями
    - Информацию о текущем активном трекере пользователя

    Возвращает:
    - Полный профиль пользователя с информацией о всех связанных трекерах и ролях
    """
    user_db = await user_repo.get_by_id_with_all_trackers(current_user_id)

    if not user_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    current_tracker_result = await user_repo.get_user_current_tracker(current_user_id)

    all_trackers_response = []
    if user_db.tracker_associations:
        for assoc in user_db.tracker_associations:
            if assoc.tracker:
                tracker_response = TrackerResponse.model_validate(assoc.tracker)
                tracker_response.role = assoc.role.value
                all_trackers_response.append(tracker_response)

    # Prepare the current tracker for the response
    current_tracker_response = None
    if current_tracker_result:
        current_tracker_db, role = current_tracker_result
        current_tracker_response = TrackerResponse.model_validate(current_tracker_db)
        current_tracker_response.role = role  # Add the user's role

    # Construct the UserResponse
    user_response = UserResponse(
        id=user_db.id,
        login=user_db.login,
        email=user_db.email,
        display_name=user_db.display_name,
        first_name=user_db.first_name,
        last_name=user_db.last_name,
        trackers=all_trackers_response,  # List of all associated trackers
        current_tracker=current_tracker_response,  # The currently active tracker
        is_active=user_db.is_active,
    )

    return user_response
