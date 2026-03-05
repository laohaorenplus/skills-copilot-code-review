"""
Announcement endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime, date

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _serialize(ann: dict) -> dict:
    """Convert a MongoDB document to a JSON-serializable dict."""
    ann["id"] = str(ann.pop("_id"))
    return ann


def _require_teacher(teacher_username: str):
    """Raise 401 if the given username is not a valid teacher."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    return teacher


def _parse_object_id(announcement_id: str) -> ObjectId:
    """Parse and return an ObjectId, raising 400 on invalid input."""
    try:
        return ObjectId(announcement_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid announcement ID")


def _validate_dates(expiration_date: str, start_date: Optional[str]) -> None:
    """Validate that date strings are well-formed and logically consistent."""
    try:
        exp = date.fromisoformat(expiration_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid expiration_date format. Use YYYY-MM-DD"
        )
    if start_date:
        try:
            start = date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid start_date format. Use YYYY-MM-DD"
            )
        if start > exp:
            raise HTTPException(
                status_code=400,
                detail="start_date must not be later than expiration_date"
            )


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """
    Get all currently active announcements (public).

    An announcement is active when today falls within its optional start_date
    and required expiration_date range.
    """
    today = date.today().isoformat()
    query = {
        "expiration_date": {"$gte": today},
        "$or": [
            {"start_date": None},
            {"start_date": {"$exists": False}},
            {"start_date": {"$lte": today}},
        ],
    }
    return [_serialize(ann) for ann in announcements_collection.find(query)]


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str) -> List[Dict[str, Any]]:
    """
    Get all announcements regardless of active status.

    Requires teacher authentication.
    """
    _require_teacher(teacher_username)
    return [_serialize(ann) for ann in announcements_collection.find()]


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    expiration_date: str,
    teacher_username: str,
    start_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new announcement.

    - **message**: The announcement text (required).
    - **expiration_date**: Last day the announcement is visible, YYYY-MM-DD (required).
    - **start_date**: First day the announcement is visible, YYYY-MM-DD (optional).
    - **teacher_username**: Authenticated teacher username (required).
    """
    _require_teacher(teacher_username)
    _validate_dates(expiration_date, start_date)

    announcement = {
        "message": message,
        "start_date": start_date or None,
        "expiration_date": expiration_date,
        "created_by": teacher_username,
        "created_at": datetime.utcnow().isoformat(),
    }
    result = announcements_collection.insert_one(announcement)
    announcement["id"] = str(result.inserted_id)
    announcement.pop("_id", None)
    return announcement


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    expiration_date: str,
    teacher_username: str,
    start_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update an existing announcement.

    Requires teacher authentication.
    """
    _require_teacher(teacher_username)
    oid = _parse_object_id(announcement_id)

    if not announcements_collection.find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail="Announcement not found")

    _validate_dates(expiration_date, start_date)

    announcements_collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "message": message,
                "start_date": start_date or None,
                "expiration_date": expiration_date,
                "updated_by": teacher_username,
                "updated_at": datetime.utcnow().isoformat(),
            }
        },
    )
    updated = announcements_collection.find_one({"_id": oid})
    return _serialize(updated)


@router.delete("/{announcement_id}", response_model=Dict[str, Any])
def delete_announcement(
    announcement_id: str,
    teacher_username: str,
) -> Dict[str, Any]:
    """
    Delete an announcement.

    Requires teacher authentication.
    """
    _require_teacher(teacher_username)
    oid = _parse_object_id(announcement_id)

    if not announcements_collection.find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail="Announcement not found")

    announcements_collection.delete_one({"_id": oid})
    return {"message": "Announcement deleted successfully"}
