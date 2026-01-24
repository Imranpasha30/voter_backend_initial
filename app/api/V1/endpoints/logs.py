from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from typing import Optional, Union, List
from datetime import date

from app.db.session import get_db
from app.models.voter_change_log import VoterChangeLog
from app.models.user import User
from app.models.volunteer import Volunteer
from app.api.deps import get_current_user, get_effective_user_id
from app.schemas.log import ChangeLogResponse, ChangeLogListResponse


router = APIRouter()


# ✅ NEW: Get list of volunteers with their change counts
@router.get("/volunteers-with-logs")
def get_volunteers_with_logs(
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of volunteers under current politician with their change counts"""
    
    # Only politicians can access this
    if hasattr(current_user, 'politician_id'):
        return {"error": "Only politicians can access this endpoint"}
    
    from app.models.volunteer import Volunteer as VolunteerModel
    
    # Get all volunteers under this politician
    volunteers = db.query(VolunteerModel).filter(
        VolunteerModel.politician_id == current_user.user_id,
        VolunteerModel.is_active == True
    ).all()
    
    volunteer_list = []
    for volunteer in volunteers:
        # Count changes made by this volunteer
        change_count = db.query(func.count(VoterChangeLog.log_id)).filter(
            VoterChangeLog.volunteer_id == volunteer.id
        ).scalar() or 0
        
        # Get last activity
        last_change = db.query(VoterChangeLog.change_timestamp).filter(
            VoterChangeLog.volunteer_id == volunteer.id
        ).order_by(desc(VoterChangeLog.change_timestamp)).first()
        
        volunteer_list.append({
            "id": volunteer.id,
            "username": volunteer.username,
            "email": volunteer.email,
            "phone_number": volunteer.phone_number,
            "total_changes": change_count,
            "last_activity": last_change[0] if last_change else None,
            "is_active": volunteer.is_active
        })
    
    # Sort by total changes (most active first)
    volunteer_list.sort(key=lambda x: x['total_changes'], reverse=True)
    
    return {
        "total_volunteers": len(volunteer_list),
        "volunteers": volunteer_list
    }


# ✅ UPDATED: Get changes by specific volunteer (for politicians)
@router.get("/volunteer/{volunteer_id}/changes", response_model=ChangeLogListResponse)
def get_volunteer_changes(
    volunteer_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    epic_no: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get change logs for a specific volunteer (politicians only)"""
    
    # Only politicians can access this
    if hasattr(current_user, 'politician_id'):
        return ChangeLogListResponse(total=0, page=1, page_size=20, logs=[])
    
    # Verify the volunteer belongs to this politician
    from app.models.volunteer import Volunteer as VolunteerModel
    volunteer = db.query(VolunteerModel).filter(
        VolunteerModel.id == volunteer_id,
        VolunteerModel.politician_id == current_user.user_id
    ).first()
    
    if not volunteer:
        return ChangeLogListResponse(total=0, page=1, page_size=20, logs=[])
    
    # Build query
    query = db.query(VoterChangeLog).filter(
        VoterChangeLog.volunteer_id == volunteer_id
    )
    
    # Apply filters
    if epic_no:
        query = query.filter(VoterChangeLog.epic_no.ilike(f"%{epic_no}%"))
    
    if from_date:
        query = query.filter(func.date(VoterChangeLog.change_timestamp) >= from_date)
    
    if to_date:
        query = query.filter(func.date(VoterChangeLog.change_timestamp) <= to_date)
    
    query = query.order_by(desc(VoterChangeLog.change_timestamp))
    
    total = query.count()
    offset = (page - 1) * page_size
    logs = query.offset(offset).limit(page_size).all()
    
    return ChangeLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        logs=logs
    )


@router.get("/my-changes", response_model=ChangeLogListResponse)
def get_my_changes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    epic_no: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get change logs for current user (politician or volunteer)"""
    
    # Build query based on user type
    if hasattr(current_user, 'politician_id'):
        # Volunteer - filter by volunteer_id
        query = db.query(VoterChangeLog).filter(
            VoterChangeLog.volunteer_id == current_user.id
        )
    else:
        # Politician - filter by user_id (only their OWN changes, not volunteers)
        query = db.query(VoterChangeLog).filter(
            VoterChangeLog.user_id == current_user.user_id
        )
    
    # Apply filters
    if epic_no:
        query = query.filter(VoterChangeLog.epic_no.ilike(f"%{epic_no}%"))
    
    if from_date:
        query = query.filter(func.date(VoterChangeLog.change_timestamp) >= from_date)
    
    if to_date:
        query = query.filter(func.date(VoterChangeLog.change_timestamp) <= to_date)
    
    query = query.order_by(desc(VoterChangeLog.change_timestamp))
    
    total = query.count()
    offset = (page - 1) * page_size
    logs = query.offset(offset).limit(page_size).all()
    
    return ChangeLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        logs=logs
    )


@router.get("/all-changes", response_model=ChangeLogListResponse)
def get_all_changes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    epic_no: Optional[str] = Query(None),
    user_type: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all change logs (Politicians see their changes + all volunteers' changes)"""
    
    # For politicians: show their changes + their volunteers' changes
    if not hasattr(current_user, 'politician_id'):
        # Get volunteer IDs under this politician
        from app.models.volunteer import Volunteer as VolunteerModel
        volunteer_ids = db.query(VolunteerModel.id).filter(
            VolunteerModel.politician_id == current_user.user_id
        ).all()
        volunteer_ids = [v.id for v in volunteer_ids]
        
        query = db.query(VoterChangeLog).filter(
            or_(
                VoterChangeLog.user_id == current_user.user_id,
                VoterChangeLog.volunteer_id.in_(volunteer_ids)
            )
        )
    else:
        # Volunteers can only see their own changes
        query = db.query(VoterChangeLog).filter(
            VoterChangeLog.volunteer_id == current_user.id
        )
    
    # Apply filters
    if epic_no:
        query = query.filter(VoterChangeLog.epic_no.ilike(f"%{epic_no}%"))
    
    if user_type:
        query = query.filter(VoterChangeLog.user_type == user_type)
    
    if from_date:
        query = query.filter(func.date(VoterChangeLog.change_timestamp) >= from_date)
    
    if to_date:
        query = query.filter(func.date(VoterChangeLog.change_timestamp) <= to_date)
    
    query = query.order_by(desc(VoterChangeLog.change_timestamp))
    
    total = query.count()
    offset = (page - 1) * page_size
    logs = query.offset(offset).limit(page_size).all()
    
    return ChangeLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        logs=logs
    )


@router.get("/voter/{epic_no}/history", response_model=ChangeLogListResponse)
def get_voter_change_history(
    epic_no: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get complete change history for a specific voter"""
    
    # Filter by user type
    if hasattr(current_user, 'politician_id'):
        # Volunteer - only show their own changes for this voter
        query = db.query(VoterChangeLog).filter(
            VoterChangeLog.epic_no == epic_no,
            VoterChangeLog.volunteer_id == current_user.id
        )
    else:
        # Politician - show all changes (their own + volunteers)
        from app.models.volunteer import Volunteer as VolunteerModel
        volunteer_ids = db.query(VolunteerModel.id).filter(
            VolunteerModel.politician_id == current_user.user_id
        ).all()
        volunteer_ids = [v.id for v in volunteer_ids]
        
        query = db.query(VoterChangeLog).filter(
            VoterChangeLog.epic_no == epic_no,
            or_(
                VoterChangeLog.user_id == current_user.user_id,
                VoterChangeLog.volunteer_id.in_(volunteer_ids)
            )
        )
    
    query = query.order_by(desc(VoterChangeLog.change_timestamp))
    
    total = query.count()
    offset = (page - 1) * page_size
    logs = query.offset(offset).limit(page_size).all()
    
    return ChangeLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        logs=logs
    )


@router.get("/stats")
def get_log_stats(
    current_user: Union[User, Volunteer] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get statistics about changes made"""
    
    from datetime import datetime, timedelta
    
    if hasattr(current_user, 'politician_id'):
        # Volunteer stats
        total_changes = db.query(func.count(VoterChangeLog.log_id)).filter(
            VoterChangeLog.volunteer_id == current_user.id
        ).scalar()
        
        unique_voters_edited = db.query(func.count(func.distinct(VoterChangeLog.voter_id))).filter(
            VoterChangeLog.volunteer_id == current_user.id
        ).scalar()
        
        # Recent activity (last 7 days)
        last_week = datetime.now() - timedelta(days=7)
        recent_changes = db.query(func.count(VoterChangeLog.log_id)).filter(
            VoterChangeLog.volunteer_id == current_user.id,
            VoterChangeLog.change_timestamp >= last_week
        ).scalar()
        
    else:
        # Politician stats (including volunteers)
        from app.models.volunteer import Volunteer as VolunteerModel
        volunteer_ids = db.query(VolunteerModel.id).filter(
            VolunteerModel.politician_id == current_user.user_id
        ).all()
        volunteer_ids = [v.id for v in volunteer_ids]
        
        total_changes = db.query(func.count(VoterChangeLog.log_id)).filter(
            or_(
                VoterChangeLog.user_id == current_user.user_id,
                VoterChangeLog.volunteer_id.in_(volunteer_ids)
            )
        ).scalar()
        
        unique_voters_edited = db.query(func.count(func.distinct(VoterChangeLog.voter_id))).filter(
            or_(
                VoterChangeLog.user_id == current_user.user_id,
                VoterChangeLog.volunteer_id.in_(volunteer_ids)
            )
        ).scalar()
        
        # Recent activity
        last_week = datetime.now() - timedelta(days=7)
        recent_changes = db.query(func.count(VoterChangeLog.log_id)).filter(
            or_(
                VoterChangeLog.user_id == current_user.user_id,
                VoterChangeLog.volunteer_id.in_(volunteer_ids)
            ),
            VoterChangeLog.change_timestamp >= last_week
        ).scalar()
    
    return {
        "total_changes": total_changes or 0,
        "unique_voters_edited": unique_voters_edited or 0,
        "recent_changes_7_days": recent_changes or 0
    }
