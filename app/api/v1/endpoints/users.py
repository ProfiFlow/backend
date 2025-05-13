import logging
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DB, CurrentUserId, TrackerSvc, UserRepo
from app.database.user import User
from app.schemas.user import UserBaseResponse, RoleUpdateRequest
from app.database.user_tracker_role import RoleEnum

router = APIRouter()

log = logging.getLogger(__name__)


@router.get("", response_model=List[UserBaseResponse])
async def get_users(
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
    tracker_service: TrackerSvc,
):
    """Get all users"""
    log.debug("Fetching all users")

    # Get users from Yandex Tracker
    tracker_users = await tracker_service.get_users(current_user_id)

    # Filter out robot users
    real_users = [
        user
        for user in tracker_users
        if not user.get("display", "").lower().startswith("робот")
    ]

    # Get current tracker for the current user
    current_tracker, role = await user_repo.get_user_current_tracker(current_user_id)
    if not current_tracker:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь не привязан к трекеру",
        )
    
    if role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для выполнения этой операции",
        )

    # Create users that don't exist in our database
    for tracker_user in real_users:
        try:
            # Extract required fields
            yandex_id = tracker_user.get("passportUid")
            email = tracker_user.get("email")
            login = tracker_user.get("login")
            first_name = tracker_user.get("firstName")
            last_name = tracker_user.get("lastName")
            display_name = tracker_user.get("display")

            if not yandex_id or not email:
                log.warning(f"Incomplete user data: {tracker_user}")
                continue

            # Check if user already exists
            existing_user = await user_repo.get_by_yandex_id(yandex_id)

            if not existing_user:
                # Create new user without tokens
                new_user = User(
                    email=email,
                    yandex_id=yandex_id,
                    login=login,
                    first_name=first_name,
                    last_name=last_name,
                    display_name=display_name,
                    is_verified=True,
                )
                await user_repo.create_user(new_user)
                # Assign employee role for the current tracker
                await user_repo.set_current_tracker(
                    new_user.id, current_tracker.id, "employee"
                )
                log.info(f"Created new user: {new_user.id} ({display_name})")
            else:
                # Check if user has role for current tracker
                user_role = await user_repo.get_user_role_for_tracker(
                    existing_user.id, current_tracker.id
                )
                if not user_role:
                    # Only assign role if the user doesn't have one for this tracker
                    await user_repo.set_current_tracker(
                        existing_user.id, current_tracker.id, "employee"
                    )
                    log.info(
                        f"Assigned employee role to user: {existing_user.id} ({existing_user.display_name})"
                    )
        except Exception as e:
            log.error(f"Error processing user {tracker_user.get('display')}: {str(e)}")

    # Get all users from database
    users = await user_repo.get_all_users()

    # Convert users to response model
    user_responses = [
        UserBaseResponse(
            id=user.id,
            login=user.login,
            email=user.email,
            display_name=user.display_name,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        for user in users
    ]

    return user_responses


@router.post("/{user_id}/role")
async def update_role(
    user_id: int,
    request: RoleUpdateRequest,
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
):
    """Update a user's role"""
    log.debug(f"Updating role for user with ID {user_id} to {request.role}")

    # Check if the user exists
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    current_tracker, current_role = await user_repo.get_user_current_tracker(
        current_user_id
    )
    if not current_tracker:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь не привязан к трекеру",
        )

    if current_role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для выполнения этой операции",
        )

    if user.id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для выполнения этой операции",
        )

    try:
        role_enum = RoleEnum(request.role)
        await user_repo.change_user_role(user_id, current_tracker.id, role_enum)
        return {"detail": "User role updated successfully"}
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {request.role}. Must be one of: {[r.value for r in RoleEnum]}"
        ) 
