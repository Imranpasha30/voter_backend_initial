from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Union
from datetime import datetime, timedelta
import uuid

from app.db.session import get_db
from app.models.user import User
from app.models.login_log import LoginLog
from app.schemas.user import UserResponse, UserCreate, UserUpdate
from app.schemas.login_log import LoginLogResponse, LoginLogsListResponse
from app.api.deps import get_current_user
from app.core.security import get_password_hash
from app.core.config import settings
from app.services.imagekit_service import imagekit_service
from app.models.volunteer import Volunteer


router = APIRouter()


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


# ─────────────────────────────────────────────
# Helper: block volunteers, only politicians
# ─────────────────────────────────────────────

def _require_politician(current_user: Union[User, Volunteer]) -> User:
    """Raises 403 if caller is a Volunteer, returns typed User otherwise."""
    if hasattr(current_user, 'politician_id'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Volunteers cannot use this endpoint. Contact your administrator.",
        )
    return current_user  # type: ignore[return-value]


# ═══════════════════════════════════════════════════════════
# /me  — own profile
# ═══════════════════════════════════════════════════════════

@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current logged-in user information including profile_image_url."""
    return current_user


@router.put("/me", response_model=UserResponse)
def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user's profile."""
    update_data = user_update.model_dump(exclude_unset=True)

    if "password" in update_data:
        update_data["password_hash"] = get_password_hash(
            update_data.pop("password")
        )

    for key, value in update_data.items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)
    return current_user


# ═══════════════════════════════════════════════════════════
# /me/profile-image  — upload & delete
# ═══════════════════════════════════════════════════════════

@router.post("/me/profile-image", response_model=UserResponse)
async def upload_profile_image(
    file: UploadFile = File(...),
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a profile image for the current politician.
    - Accepted types : JPEG, PNG, WEBP
    - Max size       : 5 MB
    - Storage        : ImageKit /VoterConnectImages/sharkify_user/
    - Old image      : deleted from ImageKit before uploading new one
    - Volunteers     : blocked (403)
    """
    user = _require_politician(current_user)

    # ── Validate content type ───────────────────
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid file type '{file.content_type}'. "
                "Allowed: image/jpeg, image/png, image/webp"
            ),
        )

    # ── Read & validate size ────────────────────
    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB.",
        )

    # ── Build unique filename ───────────────────
    ext = (
        file.filename.rsplit(".", 1)[-1].lower()
        if file.filename and "." in file.filename
        else "jpg"
    )
    unique_name = f"profile_{user.user_id}_{uuid.uuid4().hex[:8]}.{ext}"

    # ── Delete old image from ImageKit (best-effort) ──
    if getattr(user, "profile_image_file_id", None):
        try:
            imagekit_service.delete_user_profile_image(user.profile_image_file_id)
            print(f"🗑️  Deleted old profile image: {user.profile_image_file_id}")
        except Exception as ex:
            # Non-fatal — log and continue
            print(f"⚠️  Could not delete old image from ImageKit: {ex}")

    # ── Upload to ImageKit ──────────────────────
    upload_result = imagekit_service.upload_user_profile_image(
        file_bytes=file_bytes,
        file_name=unique_name,
        user_id=user.user_id,
    )

    if not upload_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ImageKit upload failed: {upload_result.get('error', 'Unknown error')}",
        )

    # ── Persist to DB ───────────────────────────
    user.profile_image_url = upload_result["url"]

    # Store file_id if your User model has the column (enables future deletion)
    if "file_id" in upload_result and hasattr(user, "profile_image_file_id"):
        user.profile_image_file_id = upload_result["file_id"]

    db.commit()
    db.refresh(user)

    print(f"✅ Profile image uploaded for {user.email}: {user.profile_image_url}")
    return user


@router.delete("/me/profile-image", response_model=UserResponse)
def remove_profile_image(
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove the current politician's profile image.
    - Deletes from ImageKit (best-effort)
    - Clears profile_image_url (and profile_image_file_id) from DB
    """
    user = _require_politician(current_user)

    if not user.profile_image_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile image found to remove.",
        )

    # ── Delete from ImageKit (best-effort) ─────
    if getattr(user, "profile_image_file_id", None):
        try:
            imagekit_service.delete_user_profile_image(user.profile_image_file_id)
            print(f"🗑️  Deleted profile image from ImageKit: {user.profile_image_file_id}")
        except Exception as ex:
            print(f"⚠️  Could not delete image from ImageKit: {ex}")

    # ── Clear from DB ───────────────────────────
    user.profile_image_url = None
    if hasattr(user, "profile_image_file_id"):
        user.profile_image_file_id = None

    db.commit()
    db.refresh(user)

    print(f"✅ Profile image removed for {user.email}")
    return user


# ═══════════════════════════════════════════════════════════
# /me/login-history
# ═══════════════════════════════════════════════════════════

@router.get("/me/login-history", response_model=LoginLogsListResponse)
def get_my_login_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(
        settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's login history (paginated)."""
    query = (
        db.query(LoginLog)
        .filter(LoginLog.user_id == current_user.user_id)
        .order_by(LoginLog.login_time.desc())
    )

    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()

    return LoginLogsListResponse(
        total=total, page=page, page_size=page_size, logs=logs
    )


# ═══════════════════════════════════════════════════════════
# /stats/overview  — MUST be before /{user_id} to avoid clash
# ═══════════════════════════════════════════════════════════

@router.get("/stats/overview")
def get_users_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user statistics overview."""
    total_users = db.query(func.count(User.user_id)).scalar()
    active_users = (
        db.query(func.count(User.user_id))
        .filter(User.is_active == True)
        .scalar()
    )

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_registrations = (
        db.query(func.count(User.user_id))
        .filter(User.created_at >= thirty_days_ago)
        .scalar()
    )

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_logins = (
        db.query(func.count(func.distinct(LoginLog.user_id)))
        .filter(LoginLog.login_time >= seven_days_ago)
        .scalar()
    )

    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": total_users - active_users,
        "recent_registrations_30d": recent_registrations,
        "recent_logins_7d": recent_logins,
    }


# ═══════════════════════════════════════════════════════════
# /{user_id}  — admin operations
# ═══════════════════════════════════════════════════════════

@router.get("/", response_model=list[UserResponse])
def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all users (admin only)."""
    return db.query(User).offset(skip).limit(limit).all()


@router.get("/{user_id}", response_model=UserResponse)
def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get specific user by ID."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/{user_id}/login-history", response_model=LoginLogsListResponse)
def get_user_login_history(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(
        settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get login history for a specific user."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = (
        db.query(LoginLog)
        .filter(LoginLog.user_id == user_id)
        .order_by(LoginLog.login_time.desc())
    )

    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()

    return LoginLogsListResponse(
        total=total, page=page, page_size=page_size, logs=logs
    )


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user details (admin only)."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_update.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = get_password_hash(
            update_data.pop("password")
        )

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete user (admin only)."""
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=400, detail="Cannot delete your own account"
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return None


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate a user account."""
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=400, detail="Cannot deactivate your own account"
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activate a user account."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    db.commit()
    db.refresh(user)
    return user
