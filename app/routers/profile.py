from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.database.repositories.user import UserRepository

# Removed unused import
from app.dependencies.auth import get_current_user
from app.schemas.tracker import TrackerResponse
from app.schemas.user import UserResponse

router = APIRouter(
    prefix="/api/profile",
    tags=["profile"],
)


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    session: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(
        get_current_user
    ),  # Corrected: get_current_user returns user_id
):
    """Get current user's profile with tracker information"""
    user_repo = UserRepository(session)

    # Fetch the user with all their tracker associations
    user_db = await user_repo.get_by_id_with_all_trackers(
        current_user_id
    )  # Use current_user_id directly

    if not user_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Fetch the current active tracker separately
    current_tracker_result = await user_repo.get_user_current_tracker(
        current_user_id
    )  # Use current_user_id directly

    # Prepare the list of all trackers for the response
    all_trackers_response = []
    if user_db.tracker_associations:
        for assoc in user_db.tracker_associations:
            if assoc.tracker:  # Make sure tracker is loaded
                tracker_response = TrackerResponse.from_orm(assoc.tracker)
                tracker_response.role = (
                    assoc.role.value
                )  # Add the user's role for this tracker
                all_trackers_response.append(tracker_response)

    # Prepare the current tracker for the response
    current_tracker_response = None
    if current_tracker_result:
        current_tracker_db, role = current_tracker_result
        current_tracker_response = TrackerResponse.from_orm(current_tracker_db)
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
