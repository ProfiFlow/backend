from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DB, CurrentUserId, TrackerRepo, UserRepo, get_user_repo, get_current_user_id, get_db
from app.database.repositories.tracker import TrackerRepository
from app.schemas.tracker import TrackerCreate, TrackerResponse

router = APIRouter()


@router.get("", response_model=List[TrackerResponse])
async def get_trackers(
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
    tracker_repo: TrackerRepo,
):
    """Get all available trackers"""

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


@router.post("", response_model=TrackerResponse)
async def create_tracker(
    tracker: TrackerCreate,
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
    tracker_repo: TrackerRepo,
):
    """Add a new tracker and set the creator as manager and current user for this tracker."""

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


@router.get("/current", response_model=TrackerResponse)
async def get_current_tracker(
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
):
    """Get the current user's active tracker"""
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


@router.put("/current/{tracker_id}")
async def set_current_tracker(
    tracker_id: int,
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
    tracker_repo: TrackerRepo,
):
    """Set current tracker for the user. Default role is employee."""

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


@router.get("/{tracker_id}", response_model=TrackerResponse)
async def get_tracker(
    tracker_id: int,
    current_user_id: CurrentUserId,
    user_repo: UserRepo,
    tracker_repo: TrackerRepo,
):
    """Get tracker by ID with user role information"""

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
