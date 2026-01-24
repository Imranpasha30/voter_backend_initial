from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional
from sqlalchemy import String

from app.db.session import get_db
from app.models.part import Part
from app.models.voter import Voter
from app.models.user_area import UserArea
from app.schemas.part import PartResponse, PartsListResponse
from app.api.deps import get_current_user
from app.models.user import User
from app.core.config import settings

router = APIRouter()


# Helper function to get user's allocated area_ids
def get_user_area_ids(user_id: int, db: Session) -> list:
    """Get all area_ids allocated to the user"""
    user_areas = db.query(UserArea.area_id).filter(UserArea.user_id == user_id).all()
    return [area.area_id for area in user_areas]


@router.get("/", response_model=PartsListResponse)
@router.get("/constituencies", response_model=PartsListResponse)
@router.get("/assembly-constituencies", response_model=PartsListResponse)
def get_all_parts(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all parts (constituencies) with voter counts - only from allocated areas"""
    # Get user's allocated area_ids
    user_area_ids = get_user_area_ids(current_user.user_id, db)
    
    if not user_area_ids:
        return PartsListResponse(
            total=0,
            page=page,
            page_size=page_size,
            parts=[]
        )
    
    query = db.query(
        Part,
        func.count(Voter.voter_id).label('voter_count')
    ).outerjoin(Voter, Part.part_id == Voter.part_id)\
     .filter(Part.area_id.in_(user_area_ids))\
     .group_by(Part.part_id)
    
    # Search filter
    if search:
        query = query.filter(
            or_(
                Part.part_name_en.ilike(f"%{search}%"),
                Part.part_name_v1.ilike(f"%{search}%"),
                Part.part_no.cast(String).ilike(f"%{search}%")
            )
        )
    
    # Order by part number
    query = query.order_by(Part.part_no)
    
    # Get total count
    total = query.count()
    
    # Pagination
    offset = (page - 1) * page_size
    results = query.offset(offset).limit(page_size).all()
    
    # Map to response
    parts = []
    for part, voter_count in results:
        part_dict = {
            "part_id": part.part_id,
            "part_no": part.part_no,
            "part_name_en": part.part_name_en,
            "part_name_v1": part.part_name_v1,
            "created_at": part.created_at,
            "voter_count": voter_count
        }
        parts.append(PartResponse(**part_dict))
    
    return PartsListResponse(
        total=total,
        page=page,
        page_size=page_size,
        parts=parts
    )


@router.get("/{part_id}", response_model=PartResponse)
def get_part_by_id(
    part_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific part by ID - only from allocated areas"""
    part = db.query(Part).filter(Part.part_id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    
    # Check if user has access to this part's area
    user_area_ids = get_user_area_ids(current_user.user_id, db)
    if part.area_id not in user_area_ids:
        raise HTTPException(
            status_code=403,
            detail="Access denied: You don't have permission to view this part"
        )
    
    voter_count = db.query(func.count(Voter.voter_id)).filter(
        Voter.part_id == part_id
    ).scalar()
    
    return PartResponse(
        part_id=part.part_id,
        part_no=part.part_no,
        part_name_en=part.part_name_en,
        part_name_v1=part.part_name_v1,
        created_at=part.created_at,
        voter_count=voter_count
    )


@router.get("/number/{part_no}", response_model=PartResponse)
def get_part_by_number(
    part_no: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific part by part number - only from allocated areas"""
    part = db.query(Part).filter(Part.part_no == part_no).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    
    # Check if user has access to this part's area
    user_area_ids = get_user_area_ids(current_user.user_id, db)
    if part.area_id not in user_area_ids:
        raise HTTPException(
            status_code=403,
            detail="Access denied: You don't have permission to view this part"
        )
    
    voter_count = db.query(func.count(Voter.voter_id)).filter(
        Voter.part_id == part.part_id
    ).scalar()
    
    return PartResponse(
        part_id=part.part_id,
        part_no=part.part_no,
        part_name_en=part.part_name_en,
        part_name_v1=part.part_name_v1,
        created_at=part.created_at,
        voter_count=voter_count
    )


@router.get("/{part_id}/voters", response_model=dict)
def get_part_voter_summary(
    part_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voter summary for a specific part - only from allocated areas"""
    part = db.query(Part).filter(Part.part_id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    
    # Check if user has access to this part's area
    user_area_ids = get_user_area_ids(current_user.user_id, db)
    if part.area_id not in user_area_ids:
        raise HTTPException(
            status_code=403,
            detail="Access denied: You don't have permission to view this part"
        )
    
    # Total voters
    total_voters = db.query(func.count(Voter.voter_id)).filter(
        Voter.part_id == part_id
    ).scalar()
    
    # Gender distribution
    gender_dist = db.query(
        Voter.gender,
        func.count(Voter.voter_id).label('count')
    ).filter(Voter.part_id == part_id).group_by(Voter.gender).all()
    
    # Average age
    avg_age = db.query(func.avg(Voter.age)).filter(
        Voter.part_id == part_id
    ).scalar()
    
    return {
        "part_id": part.part_id,
        "part_no": part.part_no,
        "part_name": part.part_name_en,
        "total_voters": total_voters,
        "gender_distribution": [{"gender": g, "count": c} for g, c in gender_dist],
        "average_age": round(float(avg_age), 2) if avg_age else None
    }


@router.get("/stats/overview")
def get_parts_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get overview statistics of all parts - only from allocated areas"""
    # Get user's allocated area_ids
    user_area_ids = get_user_area_ids(current_user.user_id, db)
    
    if not user_area_ids:
        return {
            "total_parts": 0,
            "total_voters": 0,
            "average_voters_per_part": 0,
            "top_parts": []
        }
    
    total_parts = db.query(func.count(Part.part_id)).filter(
        Part.area_id.in_(user_area_ids)
    ).scalar()
    
    total_voters = db.query(func.count(Voter.voter_id)).join(
        Part, Voter.part_id == Part.part_id
    ).filter(Part.area_id.in_(user_area_ids)).scalar()
    
    # Parts with most voters (within allocated areas)
    top_parts = db.query(
        Part.part_no,
        Part.part_name_en,
        func.count(Voter.voter_id).label('voter_count')
    ).join(Voter, Part.part_id == Voter.part_id)\
     .filter(Part.area_id.in_(user_area_ids))\
     .group_by(Part.part_id, Part.part_no, Part.part_name_en)\
     .order_by(func.count(Voter.voter_id).desc())\
     .limit(10).all()
    
    return {
        "total_parts": total_parts,
        "total_voters": total_voters,
        "average_voters_per_part": round(total_voters / total_parts, 2) if total_parts > 0 else 0,
        "top_parts": [
            {
                "part_no": p[0],
                "part_name": p[1],
                "voter_count": p[2]
            } for p in top_parts
        ]
    }
