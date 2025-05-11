from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.database.repositories.tracker import TrackerRepository
from app.database.repositories.user import UserRepository
from app.dependencies.auth import get_current_user
from app.schemas.tracker import TrackerCreate, TrackerResponse

router = APIRouter(
    prefix="/trackers",
    tags=["trackers"],
)


@router.get("", response_model=List[TrackerResponse])
async def get_trackers(
    session: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user),
):
    """Get all available trackers"""
    tracker_repo = TrackerRepository(session)
    user_repo = UserRepository(session)

    # Get all trackers
    trackers = await tracker_repo.get_all()

    # Prepare response with roles
    tracker_responses = []
    for tracker in trackers:
        response = TrackerResponse.from_orm(tracker)
        # Get role for this tracker if exists
        role = await user_repo.get_user_role_for_tracker(current_user_id, tracker.id)
        response.role = role
        tracker_responses.append(response)

    return tracker_responses


@router.post("", response_model=TrackerResponse)
async def create_tracker(
    tracker: TrackerCreate,
    session: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(
        get_current_user
    ),  # Corrected: get_current_user returns user_id
):
    """Add a new tracker and set the creator as manager and current user for this tracker."""
    tracker_repo = TrackerRepository(session)
    user_repo = UserRepository(session)

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
        user_id=current_user_id,  # Use current_user_id directly
        tracker_id=new_tracker.id,
        role="manager",  # Set role to manager
    )
    return new_tracker


@router.get("/current", response_model=TrackerResponse)
async def get_current_tracker(
    session: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(
        get_current_user
    ),  # Corrected: get_current_user returns user_id
):
    """Get the current user's active tracker"""
    user_repo = UserRepository(session)
    result = await user_repo.get_user_current_tracker(
        current_user_id
    )  # Use current_user_id directly

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active tracker set for this user",
        )

    active_tracker, role = result
    response = TrackerResponse.from_orm(active_tracker)
    response.role = role

    return response


@router.put("/current/{tracker_id}")
async def set_current_tracker(
    tracker_id: int,
    session: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(
        get_current_user
    ),  # Corrected: get_current_user returns user_id
):
    """Set current tracker for the user. Default role is employee."""
    tracker_repo = TrackerRepository(session)
    user_repo = UserRepository(session)

    tracker_db = await tracker_repo.get_by_id(tracker_id)
    if not tracker_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tracker not found"
        )

    await user_repo.set_current_tracker(
        user_id=current_user_id,  # Use current_user_id directly
        tracker_id=tracker_db.id,
    )

    # Get the role for this tracker
    role = await user_repo.get_user_role_for_tracker(current_user_id, tracker_db.id)

    # Create response with role information
    tracker_response = TrackerResponse.from_orm(tracker_db)
    tracker_response.role = role

    return {
        "message": "Tracker successfully set as current",
        "tracker": tracker_response,
    }


@router.get("/{tracker_id}", response_model=TrackerResponse)
async def get_tracker(
    tracker_id: int,
    session: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user),
):
    """Get tracker by ID with user role information"""
    tracker_repo = TrackerRepository(session)
    user_repo = UserRepository(session)

    # Get the tracker
    tracker = await tracker_repo.get_by_id(tracker_id)
    if not tracker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tracker not found"
        )

    # Get the user's role for this tracker
    response = TrackerResponse.from_orm(tracker)
    role = await user_repo.get_user_role_for_tracker(current_user_id, tracker_id)
    response.role = role

    return response
