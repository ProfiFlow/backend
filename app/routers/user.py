import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.database.repositories.user import UserRepository
from app.database.user import User
from app.dependencies.auth import get_current_user
from app.schemas.user import UserBaseResponse, UserResponse
from app.services.yandex_tracker import YandexTrackerService

router = APIRouter(
    prefix="/users",
    tags=["users"],
)

log = logging.getLogger(__name__)


@router.get("", response_model=List[UserBaseResponse])
async def get_users(
    session: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user),
):
    """Get all users"""
    log.debug("Fetching all users")
    user_repo = UserRepository(session)
    yandex = YandexTrackerService(session)

    # Get users from Yandex Tracker
    tracker_users = await yandex.get_users(current_user_id)

    # Filter out robot users
    real_users = [
        user
        for user in tracker_users
        if not user.get("display", "").lower().startswith("робот")
    ]

    # Get current tracker for the current user
    current_tracker_result = await user_repo.get_user_current_tracker(current_user_id)
    if not current_tracker_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь не привязан к трекеру",
        )

    current_tracker, _ = current_tracker_result

    # Create users that don't exist in our database
    for tracker_user in real_users:
        try:
            # Extract required fields
            yandex_id = tracker_user.get("passportUid")
            email = tracker_user.get("email")
            tracker_uid = tracker_user.get("trackerUid")
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
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)

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

    # Get all users from database and convert to UserResponse objects
    result = await session.execute(select(User))
    users = result.scalars().all()

    # Convert SQLAlchemy User objects to Pydantic UserResponse objects
    user_responses = []
    for user in users:
        user_response = UserBaseResponse(
            id=user.id,
            login=user.login,
            email=user.email,
            display_name=user.display_name,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        user_responses.append(user_response)

    return user_responses
