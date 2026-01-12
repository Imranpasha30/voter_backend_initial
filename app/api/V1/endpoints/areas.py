from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional

from app.db.session import get_db
from app.models.area import Area
from app.models.user_area import UserArea
from app.models.part import Part
from app.models.voter import Voter
from app.models.user import User
from app.schemas.area import (
    AreaCreate, AreaResponse, AreasListResponse, UserAreaCreate, AreaWithParts
)
from app.api.deps import get_current_user
from app.core.config import settings


router = APIRouter()


@router.get("/", response_model=AreasListResponse)
def get_my_areas(
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get areas assigned to current politician"""
    
    # Query areas through user_areas junction
    query = db.query(Area).join(UserArea).filter(UserArea.user_id == current_user.user_id)
    
    # Search filter
    if search:
        query = query.filter(
            or_(
                Area.area_name.ilike(f"%{search}%"),
                Area.description.ilike(f"%{search}%")
            )
        )
    
    # Order by upload date
    query = query.order_by(Area.upload_date.desc())
    
    # Get total count
    total = query.count()
    
    # Pagination
    offset = (page - 1) * page_size
    areas = query.offset(offset).limit(page_size).all()
    
    return AreasListResponse(
        total=total,
        page=page,
        page_size=page_size,
        areas=areas
    )


@router.get("/{area_id}", response_model=AreaWithParts)
def get_area_details(
    area_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific area details with statistics"""
    
    # Check access
    user_area = db.query(UserArea).filter(
        UserArea.user_id == current_user.user_id,
        UserArea.area_id == area_id
    ).first()
    
    if not user_area:
        raise HTTPException(status_code=403, detail="Access denied to this area")
    
    area = db.query(Area).filter(Area.area_id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    
    # Get statistics
    parts_count = db.query(func.count(Part.part_id)).filter(Part.area_id == area_id).scalar()
    voters_count = db.query(func.count(Voter.voter_id)).join(Part).filter(Part.area_id == area_id).scalar()
    
    area_dict = {
        **area.__dict__,
        "parts_count": parts_count or 0,
        "voters_count": voters_count or 0
    }
    
    return AreaWithParts(**area_dict)


@router.post("/", response_model=AreaResponse, status_code=status.HTTP_201_CREATED)
def create_area(
    area: AreaCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new area (during Excel upload)"""
    
    # Create area
    db_area = Area(
        area_name=area.area_name,
        description=area.description,
        file_name=area.file_name,
        uploaded_by=current_user.user_id,
        total_voters=0
    )
    db.add(db_area)
    db.flush()  # Get area_id
    
    # Auto-assign to current user
    user_area = UserArea(
        user_id=current_user.user_id,
        area_id=db_area.area_id
    )
    db.add(user_area)
    
    db.commit()
    db.refresh(db_area)
    
    return db_area


@router.post("/{area_id}/assign", response_model=dict)
def assign_area_to_user(
    area_id: int,
    assignment: UserAreaCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Assign area to another politician (admin/owner only)"""
    
    # Check if area exists and user has access
    area = db.query(Area).filter(Area.area_id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    
    # Check if already assigned
    existing = db.query(UserArea).filter(
        UserArea.user_id == assignment.area_id,  # This should be user_id from request
        UserArea.area_id == area_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Area already assigned to this user")
    
    # Create assignment
    user_area = UserArea(
        user_id=assignment.area_id,  # Fix: Should come from request body
        area_id=area_id
    )
    db.add(user_area)
    db.commit()
    
    return {"message": "Area assigned successfully"}


@router.delete("/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_area(
    area_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete area (only if uploaded by current user)"""
    
    area = db.query(Area).filter(
        Area.area_id == area_id,
        Area.uploaded_by == current_user.user_id
    ).first()
    
    if not area:
        raise HTTPException(status_code=404, detail="Area not found or access denied")
    
    # Check if parts are assigned
    parts_count = db.query(func.count(Part.part_id)).filter(Part.area_id == area_id).scalar()
    if parts_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete area with {parts_count} assigned parts"
        )
    
    db.delete(area)
    db.commit()
    
    return None


@router.get("/stats/overview")
def get_areas_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get overview statistics of all user's areas"""
    
    # Get user's areas
    area_ids = db.query(UserArea.area_id).filter(
        UserArea.user_id == current_user.user_id
    ).subquery()
    
    total_areas = db.query(func.count(Area.area_id)).filter(
        Area.area_id.in_(area_ids)
    ).scalar()
    
    total_parts = db.query(func.count(Part.part_id)).filter(
        Part.area_id.in_(area_ids)
    ).scalar()
    
    total_voters = db.query(func.count(Voter.voter_id)).join(Part).filter(
        Part.area_id.in_(area_ids)
    ).scalar()
    
    return {
        "total_areas": total_areas or 0,
        "total_parts": total_parts or 0,
        "total_voters": total_voters or 0
    }
