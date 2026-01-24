from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional

from app.db.session import get_db
from app.models.voter import Voter
from app.models.part import Part
from app.models.user_area import UserArea
from app.schemas.voter import (
    VoterCreate, VoterUpdate, VoterResponse, VotersListResponse
)
from app.api.deps import get_current_user
from app.models.user import User
from app.core.config import settings
from app.models.volunteer import Volunteer

router = APIRouter()


@router.get("/", response_model=VotersListResponse)
def get_voters_by_part(
    ac_no: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voters by part number (assembly constituency)"""
    # Get part_id from part_no (Flutter sends as ac_no)
    part = db.query(Part).filter(Part.part_no == ac_no).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    
    query = db.query(Voter).filter(Voter.part_id == part.part_id)
    
    # Search filter
    if search:
        query = query.filter(
            or_(
                Voter.fm_name_en.ilike(f"%{search}%"),
                Voter.lastname_en.ilike(f"%{search}%"),
                Voter.epic_no.ilike(f"%{search}%"),
                Voter.mobile_no.ilike(f"%{search}%")
            )
        )
    
    # Order by serial number
    query = query.order_by(Voter.slnoinpart)
    
    # Get total count
    total = query.count()
    
    # Pagination
    offset = (page - 1) * page_size
    voters = query.offset(offset).limit(page_size).all()
    
    return VotersListResponse(
        total=total,
        page=page,
        page_size=page_size,
        voters=voters
    )


@router.get("/search", response_model=VotersListResponse)
def search_voters(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search voters globally by name, EPIC, or mobile"""
    query = db.query(Voter).filter(
        or_(
            Voter.fm_name_en.ilike(f"%{q}%"),
            Voter.lastname_en.ilike(f"%{q}%"),
            Voter.epic_no.ilike(f"%{q}%"),
            Voter.mobile_no.ilike(f"%{q}%")
        )
    )
    
    # Get total count
    total = query.count()
    
    # Pagination
    offset = (page - 1) * page_size
    voters = query.offset(offset).limit(page_size).all()
    
    return VotersListResponse(
        total=total,
        page=page,
        page_size=page_size,
        voters=voters
    )


@router.get("/{epic_no}", response_model=VoterResponse)
def get_voter_by_epic(
    epic_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voter details by EPIC number"""
    voter = db.query(Voter).filter(Voter.epic_no == epic_no).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    # Get part information
    part = db.query(Part).filter(Part.part_id == voter.part_id).first()
    
    # Create response with part details
    voter_dict = voter.__dict__.copy()
    voter_dict['part_no'] = part.part_no if part else None
    voter_dict['part_name'] = part.part_name_en if part else None
    
    return VoterResponse(**voter_dict)


@router.get("/id/{voter_id}", response_model=VoterResponse)
def get_voter_by_id(
    voter_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voter details by voter ID"""
    voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    # Get part information
    part = db.query(Part).filter(Part.part_id == voter.part_id).first()
    
    voter_dict = voter.__dict__.copy()
    voter_dict['part_no'] = part.part_no if part else None
    voter_dict['part_name'] = part.part_name_en if part else None
    
    return VoterResponse(**voter_dict)


@router.post("/", response_model=VoterResponse, status_code=status.HTTP_201_CREATED)
def create_voter(
    voter: VoterCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new voter"""
    # Check if EPIC already exists
    existing = db.query(Voter).filter(Voter.epic_no == voter.epic_no).first()
    if existing:
        raise HTTPException(status_code=400, detail="EPIC number already exists")
    
    # Verify part exists
    part = db.query(Part).filter(Part.part_id == voter.part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    
    # Create voter
    db_voter = Voter(**voter.model_dump())
    db.add(db_voter)
    db.commit()
    db.refresh(db_voter)
    
    return db_voter


@router.put("/{voter_id}", response_model=VoterResponse)
def update_voter(
    voter_id: int,
    voter_update: VoterUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update voter details"""
    voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    # Update only provided fields
    update_data = voter_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(voter, key, value)
    
    db.commit()
    db.refresh(voter)
    
    return voter


@router.patch("/{voter_id}", response_model=VoterResponse)
def partial_update_voter(
    voter_id: int,
    voter_update: VoterUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Partially update voter details"""
    voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    # Update only provided fields
    update_data = voter_update.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in update_data.items():
        setattr(voter, key, value)
    
    db.commit()
    db.refresh(voter)
    
    return voter


@router.delete("/{voter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voter(
    voter_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete voter"""
    voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    db.delete(voter)
    db.commit()
    
    return None


@router.get("/stats/summary")
def get_voter_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voter statistics"""
    total_voters = db.query(func.count(Voter.voter_id)).scalar()
    
    # Gender distribution
    gender_stats = db.query(
        Voter.gender,
        func.count(Voter.voter_id).label('count')
    ).group_by(Voter.gender).all()
    
    # Age groups
    age_stats = db.query(
        func.case(
            (Voter.age < 25, '18-24'),
            (Voter.age < 35, '25-34'),
            (Voter.age < 45, '35-44'),
            (Voter.age < 55, '45-54'),
            (Voter.age < 65, '55-64'),
            else_='65+'
        ).label('age_group'),
        func.count(Voter.voter_id).label('count')
    ).group_by('age_group').all()
    
    return {
        "total_voters": total_voters,
        "gender_distribution": [{"gender": g, "count": c} for g, c in gender_stats],
        "age_distribution": [{"age_group": a, "count": c} for a, c in age_stats]
    }




# ✅ Helper function to check user access to voter
def check_voter_access(voter: Voter, user_id: int, db: Session) -> bool:
    """Check if user has access to this voter's area"""
    user_area_ids = db.query(UserArea.area_id).filter(
        UserArea.user_id == user_id
    ).all()
    user_area_ids = [area.area_id for area in user_area_ids]
    
    if not user_area_ids:
        return False
    
    # Get voter's part area_id
    part = db.query(Part).filter(Part.part_id == voter.part_id).first()
    if not part or part.area_id not in user_area_ids:
        return False
    
    return True


# ✅ UPDATE VOTER ENDPOINT - SAFE VERSION
@router.patch("/{epic_no}/update", response_model=VoterResponse)
def update_voter_by_epic(
    epic_no: str,
    voter_update: VoterUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update voter details safely with validation and access control.
    Only updates provided fields (partial update).
    """
    try:
        # 1. Find voter
        voter = db.query(Voter).filter(Voter.epic_no == epic_no).first()
        if not voter:
            raise HTTPException(status_code=404, detail="Voter not found")
        
        # 2. Check access control
        if not check_voter_access(voter, current_user.user_id, db):
            raise HTTPException(
                status_code=403,
                detail="Access denied: You don't have permission to edit this voter"
            )
        
        # 3. Validate part_id change (if provided)
        update_data = voter_update.model_dump(exclude_unset=True, exclude_none=True)
        
        if 'part_id' in update_data:
            new_part = db.query(Part).filter(Part.part_id == update_data['part_id']).first()
            if not new_part:
                raise HTTPException(status_code=404, detail="Invalid part_id")
            
            # Check if user has access to new part's area
            user_area_ids = [area.area_id for area in db.query(UserArea.area_id).filter(
                UserArea.user_id == current_user.user_id
            ).all()]
            
            if new_part.area_id not in user_area_ids:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: You cannot move voter to this constituency"
                )
        
        # 4. Update voter fields (only provided fields)
        for key, value in update_data.items():
            if hasattr(voter, key):
                setattr(voter, key, value)
        
        # 5. Commit with transaction safety
        db.commit()
        db.refresh(voter)
        
        # 6. Get part information for response
        part = db.query(Part).filter(Part.part_id == voter.part_id).first()
        
        # 7. Build response
        voter_dict = {
            **voter.__dict__,
            'part_no': part.part_no if part else None,
            'part_name': part.part_name_en if part else None
        }
        
        return VoterResponse(**voter_dict)
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update voter: {str(e)}"
        )


# ✅ ALTERNATIVE: Update by voter_id
@router.patch("/id/{voter_id}/update", response_model=VoterResponse)
def update_voter_by_id(
    voter_id: int,
    voter_update: VoterUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update voter by voter_id"""
    try:
        voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
        if not voter:
            raise HTTPException(status_code=404, detail="Voter not found")
        
        if not check_voter_access(voter, current_user.user_id, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        update_data = voter_update.model_dump(exclude_unset=True, exclude_none=True)
        
        for key, value in update_data.items():
            if hasattr(voter, key):
                setattr(voter, key, value)
        
        db.commit()
        db.refresh(voter)
        
        part = db.query(Part).filter(Part.part_id == voter.part_id).first()
        voter_dict = {
            **voter.__dict__,
            'part_no': part.part_no if part else None,
            'part_name': part.part_name_en if part else None
        }
        
        return VoterResponse(**voter_dict)
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update voter: {str(e)}")
    

def get_effective_user_id(current_user, db: Session) -> int:
    """
    Returns the user_id to use for filtering data.
    - If current_user is a Politician (User model): return their user_id
    - If current_user is a Volunteer: return their politician_id (parent)
    """
    # Check if it's a Volunteer (they don't have user_id, they have 'id')
    if hasattr(current_user, 'politician_id'):
        # This is a Volunteer - return their parent politician's ID
        return current_user.politician_id
    else:
        # This is a Politician (User) - return their own ID
        return current_user.user_id
