from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional, Union

from app.db.session import get_db
from app.models.voter import Voter
from app.models.part import Part
from app.models.user_area import UserArea
from app.schemas.voter import (
    VoterCreate, VoterUpdate, VoterResponse, VotersListResponse
)
from app.api.deps import get_current_user
from app.models.user import User
from app.models.volunteer import Volunteer
from app.core.config import settings
from app.services.audit_logger import AuditLogger  # ✅ Import audit logger


router = APIRouter()


# ✅ Helper function to get effective user ID
def get_effective_user_id(current_user: Union[User, Volunteer]) -> int:
    """
    Returns the user_id to use for filtering data.
    - If current_user is a Politician (User model): return their user_id
    - If current_user is a Volunteer: return their politician_id (parent)
    """
    if hasattr(current_user, 'politician_id'):
        # This is a Volunteer - return their parent politician's ID
        return current_user.politician_id
    else:
        # This is a Politician (User) - return their own ID
        return current_user.user_id


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


# ==================== VOTER ENDPOINTS ====================

@router.get("/", response_model=VotersListResponse)
def get_voters_by_part(
    ac_no: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    search: Optional[str] = None,
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voters by part number (assembly constituency) - works for Politicians and Volunteers"""
    
    effective_user_id = get_effective_user_id(current_user)
    
    user_area_ids = db.query(UserArea.area_id).filter(
        UserArea.user_id == effective_user_id
    ).all()
    user_area_ids = [area.area_id for area in user_area_ids]
    
    if not user_area_ids:
        raise HTTPException(status_code=403, detail="No areas assigned to your account")
    
    part = db.query(Part).filter(Part.part_no == ac_no).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    
    if part.area_id not in user_area_ids:
        raise HTTPException(status_code=403, detail="Access denied to this constituency")
    
    query = db.query(Voter).filter(Voter.part_id == part.part_id)
    
    if search:
        query = query.filter(
            or_(
                Voter.fm_name_en.ilike(f"%{search}%"),
                Voter.lastname_en.ilike(f"%{search}%"),
                Voter.epic_no.ilike(f"%{search}%"),
                Voter.mobile_no.ilike(f"%{search}%")
            )
        )
    
    query = query.order_by(Voter.slnoinpart)
    total = query.count()
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
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search voters globally by name, EPIC, or mobile - respects user's assigned areas"""
    
    effective_user_id = get_effective_user_id(current_user)
    
    user_area_ids = db.query(UserArea.area_id).filter(
        UserArea.user_id == effective_user_id
    ).all()
    user_area_ids = [area.area_id for area in user_area_ids]
    
    if not user_area_ids:
        return VotersListResponse(total=0, page=page, page_size=page_size, voters=[])
    
    part_ids = db.query(Part.part_id).filter(Part.area_id.in_(user_area_ids)).all()
    part_ids = [p.part_id for p in part_ids]
    
    if not part_ids:
        return VotersListResponse(total=0, page=page, page_size=page_size, voters=[])
    
    query = db.query(Voter).filter(
        Voter.part_id.in_(part_ids),
        or_(
            Voter.fm_name_en.ilike(f"%{q}%"),
            Voter.lastname_en.ilike(f"%{q}%"),
            Voter.epic_no.ilike(f"%{q}%"),
            Voter.mobile_no.ilike(f"%{q}%")
        )
    )
    
    total = query.count()
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
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voter details by EPIC number - with access control"""
    
    effective_user_id = get_effective_user_id(current_user)
    
    voter = db.query(Voter).filter(Voter.epic_no == epic_no).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    if not check_voter_access(voter, effective_user_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this voter")
    
    part = db.query(Part).filter(Part.part_id == voter.part_id).first()
    
    voter_dict = voter.__dict__.copy()
    voter_dict['part_no'] = part.part_no if part else None
    voter_dict['part_name'] = part.part_name_en if part else None
    
    return VoterResponse(**voter_dict)


@router.get("/id/{voter_id}", response_model=VoterResponse)
def get_voter_by_id(
    voter_id: int,
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voter details by voter ID - with access control"""
    
    effective_user_id = get_effective_user_id(current_user)
    
    voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    if not check_voter_access(voter, effective_user_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this voter")
    
    part = db.query(Part).filter(Part.part_id == voter.part_id).first()
    
    voter_dict = voter.__dict__.copy()
    voter_dict['part_no'] = part.part_no if part else None
    voter_dict['part_name'] = part.part_name_en if part else None
    
    return VoterResponse(**voter_dict)


@router.post("/", response_model=VoterResponse, status_code=status.HTTP_201_CREATED)
def create_voter(
    voter: VoterCreate,
    request: Request,  # ✅ Add Request for audit logging
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new voter - with access control and audit logging"""
    
    effective_user_id = get_effective_user_id(current_user)
    
    existing = db.query(Voter).filter(Voter.epic_no == voter.epic_no).first()
    if existing:
        raise HTTPException(status_code=400, detail="EPIC number already exists")
    
    part = db.query(Part).filter(Part.part_id == voter.part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    
    user_area_ids = db.query(UserArea.area_id).filter(
        UserArea.user_id == effective_user_id
    ).all()
    user_area_ids = [area.area_id for area in user_area_ids]
    
    if part.area_id not in user_area_ids:
        raise HTTPException(status_code=403, detail="Access denied to create voter in this area")
    
    # Create voter
    db_voter = Voter(**voter.model_dump())
    db.add(db_voter)
    db.commit()
    db.refresh(db_voter)
    
    # ✅ Log creation
    try:
        AuditLogger.log_voter_change(
            db=db,
            voter_id=db_voter.voter_id,
            epic_no=db_voter.epic_no,
            current_user=current_user,
            action_type='CREATE',
            field_changed='voter_created',
            new_value='New voter created',
            ip_address=request.client.host if request.client else None,
            device_info=request.headers.get('user-agent')
        )
        db.commit()
    except Exception as e:
        print(f"Audit log error: {e}")
    
    return db_voter


@router.put("/{voter_id}", response_model=VoterResponse)
def update_voter(
    voter_id: int,
    voter_update: VoterUpdate,
    request: Request,  # ✅ Add Request
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update voter details - with access control and audit logging"""
    
    effective_user_id = get_effective_user_id(current_user)
    
    voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    if not check_voter_access(voter, effective_user_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # ✅ Track changes
    update_data = voter_update.model_dump(exclude_unset=True)
    changes = {}
    
    for key, new_value in update_data.items():
        old_value = getattr(voter, key, None)
        if old_value != new_value:
            changes[key] = {'old': old_value, 'new': new_value}
            setattr(voter, key, new_value)
    
    db.commit()
    db.refresh(voter)
    
    # ✅ Log changes
    if changes:
        try:
            AuditLogger.log_multiple_changes(
                db=db,
                voter_id=voter.voter_id,
                epic_no=voter.epic_no,
                current_user=current_user,
                action_type='UPDATE',
                changes=changes,
                ip_address=request.client.host if request.client else None,
                device_info=request.headers.get('user-agent')
            )
            db.commit()
        except Exception as e:
            print(f"Audit log error: {e}")
    
    return voter


@router.patch("/{voter_id}", response_model=VoterResponse)
def partial_update_voter(
    voter_id: int,
    voter_update: VoterUpdate,
    request: Request,  # ✅ Add Request
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Partially update voter details - with access control and audit logging"""
    
    effective_user_id = get_effective_user_id(current_user)
    
    voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    if not check_voter_access(voter, effective_user_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # ✅ Track changes
    update_data = voter_update.model_dump(exclude_unset=True, exclude_none=True)
    changes = {}
    
    for key, new_value in update_data.items():
        old_value = getattr(voter, key, None)
        if old_value != new_value:
            changes[key] = {'old': old_value, 'new': new_value}
            setattr(voter, key, new_value)
    
    db.commit()
    db.refresh(voter)
    
    # ✅ Log changes
    if changes:
        try:
            AuditLogger.log_multiple_changes(
                db=db,
                voter_id=voter.voter_id,
                epic_no=voter.epic_no,
                current_user=current_user,
                action_type='UPDATE',
                changes=changes,
                ip_address=request.client.host if request.client else None,
                device_info=request.headers.get('user-agent')
            )
            db.commit()
        except Exception as e:
            print(f"Audit log error: {e}")
    
    return voter


@router.delete("/{voter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voter(
    voter_id: int,
    request: Request,  # ✅ Add Request
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete voter - with access control and audit logging"""
    
    effective_user_id = get_effective_user_id(current_user)
    
    voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    if not check_voter_access(voter, effective_user_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # ✅ Log deletion before deleting
    epic_no = voter.epic_no
    try:
        AuditLogger.log_voter_change(
            db=db,
            voter_id=voter.voter_id,
            epic_no=epic_no,
            current_user=current_user,
            action_type='DELETE',
            field_changed='voter_deleted',
            old_value=f'Voter {voter.fm_name_en} {voter.lastname_en}',
            ip_address=request.client.host if request.client else None,
            device_info=request.headers.get('user-agent')
        )
        db.commit()
    except Exception as e:
        print(f"Audit log error: {e}")
    
    db.delete(voter)
    db.commit()
    
    return None


@router.get("/stats/summary")
def get_voter_statistics(
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voter statistics - respects user's assigned areas"""
    
    effective_user_id = get_effective_user_id(current_user)
    
    user_area_ids = db.query(UserArea.area_id).filter(
        UserArea.user_id == effective_user_id
    ).all()
    user_area_ids = [area.area_id for area in user_area_ids]
    
    if not user_area_ids:
        return {
            "total_voters": 0,
            "gender_distribution": [],
            "age_distribution": []
        }
    
    part_ids = db.query(Part.part_id).filter(Part.area_id.in_(user_area_ids)).all()
    part_ids = [p.part_id for p in part_ids]
    
    if not part_ids:
        return {
            "total_voters": 0,
            "gender_distribution": [],
            "age_distribution": []
        }
    
    total_voters = db.query(func.count(Voter.voter_id)).filter(
        Voter.part_id.in_(part_ids)
    ).scalar()
    
    gender_stats = db.query(
        Voter.gender,
        func.count(Voter.voter_id).label('count')
    ).filter(Voter.part_id.in_(part_ids)).group_by(Voter.gender).all()
    
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
    ).filter(Voter.part_id.in_(part_ids)).group_by('age_group').all()
    
    return {
        "total_voters": total_voters,
        "gender_distribution": [{"gender": g, "count": c} for g, c in gender_stats],
        "age_distribution": [{"age_group": a, "count": c} for a, c in age_stats]
    }


# ==================== UPDATE ENDPOINTS WITH AUDIT LOGGING ====================

@router.patch("/{epic_no}/update", response_model=VoterResponse)
def update_voter_by_epic(
    epic_no: str,
    voter_update: VoterUpdate,
    request: Request,  # ✅ Add Request
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update voter details with audit logging - works for Politicians and Volunteers"""
    try:
        effective_user_id = get_effective_user_id(current_user)
        
        voter = db.query(Voter).filter(Voter.epic_no == epic_no).first()
        if not voter:
            raise HTTPException(status_code=404, detail="Voter not found")
        
        if not check_voter_access(voter, effective_user_id, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        update_data = voter_update.model_dump(exclude_unset=True, exclude_none=True)
        
        if 'part_id' in update_data:
            new_part = db.query(Part).filter(Part.part_id == update_data['part_id']).first()
            if not new_part:
                raise HTTPException(status_code=404, detail="Invalid part_id")
            
            user_area_ids = [area.area_id for area in db.query(UserArea.area_id).filter(
                UserArea.user_id == effective_user_id
            ).all()]
            
            if new_part.area_id not in user_area_ids:
                raise HTTPException(status_code=403, detail="Access denied: Cannot move voter to this constituency")
        
        # ✅ Track changes for audit log
        changes = {}
        for key, new_value in update_data.items():
            if hasattr(voter, key):
                old_value = getattr(voter, key)
                if old_value != new_value:
                    changes[key] = {'old': old_value, 'new': new_value}
                    setattr(voter, key, new_value)
        
        db.commit()
        db.refresh(voter)
        
        # ✅ Log all changes
        if changes:
            try:
                AuditLogger.log_multiple_changes(
                    db=db,
                    voter_id=voter.voter_id,
                    epic_no=voter.epic_no,
                    current_user=current_user,
                    action_type='UPDATE',
                    changes=changes,
                    ip_address=request.client.host if request.client else None,
                    device_info=request.headers.get('user-agent')
                )
                db.commit()
            except Exception as e:
                print(f"Audit log error: {e}")
        
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


@router.patch("/id/{voter_id}/update", response_model=VoterResponse)
def update_voter_by_id(
    voter_id: int,
    voter_update: VoterUpdate,
    request: Request,  # ✅ Add Request
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update voter by voter_id with audit logging"""
    try:
        effective_user_id = get_effective_user_id(current_user)
        
        voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
        if not voter:
            raise HTTPException(status_code=404, detail="Voter not found")
        
        if not check_voter_access(voter, effective_user_id, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        update_data = voter_update.model_dump(exclude_unset=True, exclude_none=True)
        
        # ✅ Track changes
        changes = {}
        for key, new_value in update_data.items():
            if hasattr(voter, key):
                old_value = getattr(voter, key)
                if old_value != new_value:
                    changes[key] = {'old': old_value, 'new': new_value}
                    setattr(voter, key, new_value)
        
        db.commit()
        db.refresh(voter)
        
        # ✅ Log changes
        if changes:
            try:
                AuditLogger.log_multiple_changes(
                    db=db,
                    voter_id=voter.voter_id,
                    epic_no=voter.epic_no,
                    current_user=current_user,
                    action_type='UPDATE',
                    changes=changes,
                    ip_address=request.client.host if request.client else None,
                    device_info=request.headers.get('user-agent')
                )
                db.commit()
            except Exception as e:
                print(f"Audit log error: {e}")
        
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
