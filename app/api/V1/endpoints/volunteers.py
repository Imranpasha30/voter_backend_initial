from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional, List
from datetime import date

from app.db.session import get_db
from app.models.volunteer import Volunteer
from app.models.form_data import FormData
from app.models.family_member import FamilyMember
from app.models.user import User
from app.schemas.volunteer import VolunteerCreate, VolunteerResponse, VolunteerUpdate
from app.schemas.form_data import (
    FormDataCreate, FormDataResponse, MapPinResponse,
    DashboardSummaryResponse, VoterDemographicsResponse, PoliticalSupportResponse
)
from app.api.deps import get_current_user
import json

router = APIRouter()

# ========================================
# VOLUNTEER MANAGEMENT
# ========================================

@router.post("/", response_model=VolunteerResponse, status_code=201)
def create_volunteer(
    volunteer: VolunteerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new volunteer under current politician"""
    
    # Check if email already exists
    existing = db.query(Volunteer).filter(Volunteer.email == volunteer.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # ✅ Store plain password (no hashing)
    db_volunteer = Volunteer(
        politician_id=current_user.user_id,
        username=volunteer.username,
        email=volunteer.email,
        password=volunteer.password,  # ✅ Plain password
        phone_number=volunteer.phone_number,
        is_active=True
    )
    db.add(db_volunteer)
    db.commit()
    db.refresh(db_volunteer)
    
    return db_volunteer


@router.get("/", response_model=List[VolunteerResponse])
def get_my_volunteers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all volunteers under current politician"""
    volunteers = db.query(Volunteer).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()
    return volunteers


@router.put("/{volunteer_id}", response_model=VolunteerResponse)
def update_volunteer(
    volunteer_id: int,
    volunteer_update: VolunteerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update volunteer details"""
    volunteer = db.query(Volunteer).filter(
        Volunteer.id == volunteer_id,
        Volunteer.politician_id == current_user.user_id
    ).first()
    
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    if volunteer_update.username:
        volunteer.username = volunteer_update.username
    if volunteer_update.phone_number:
        volunteer.phone_number = volunteer_update.phone_number
    if volunteer_update.is_active is not None:
        volunteer.is_active = volunteer_update.is_active
    
    db.commit()
    db.refresh(volunteer)
    return volunteer

# ✅ ADD: Reset Password Endpoint (Politician can reset volunteer password)
@router.patch("/{volunteer_id}/reset-password", response_model=dict)
def reset_volunteer_password(
    volunteer_id: int,
    new_password: str = Query(..., min_length=6),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset volunteer password (politician only)"""
    volunteer = db.query(Volunteer).filter(
        Volunteer.id == volunteer_id,
        Volunteer.politician_id == current_user.user_id
    ).first()
    
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    # Update password
    volunteer.password = new_password
    db.commit()
    
    return {
        "message": "Password reset successfully",
        "email": volunteer.email,
        "new_password": new_password  # Send back to politician so they can share
    }


# ========================================
# FORM DATA SUBMISSION
# ========================================

@router.post("/form", response_model=dict)
async def submit_form(
    volunteer_id: int = Form(...),
    household_name: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    colony: Optional[str] = Form(None),
    family_members: Optional[int] = Form(0),
    voter_id: Optional[str] = Form(None),
    aadhar: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    knows_corporator: Optional[bool] = Form(None),
    satisfied_with_corporator: Optional[bool] = Form(None),
    knows_politician: Optional[bool] = Form(None),
    supports_politician: Optional[str] = Form(None),
    politician_visit_freq: Optional[str] = Form(None),
    services: Optional[str] = Form(None),
    service_frequency: Optional[str] = Form(None),
    service_satisfaction: Optional[str] = Form(None),
    attended_events: Optional[bool] = Form(None),
    income_range: Optional[str] = Form(None),
    main_occupation: Optional[str] = Form(None),
    education: Optional[str] = Form(None),
    housing_type: Optional[str] = Form(None),
    children_count: Optional[int] = Form(0),
    visit_date: Optional[str] = Form(None),
    volunteer_name: Optional[str] = Form(None),
    corporator_division: Optional[str] = Form(None),
    zone: Optional[str] = Form(None),
    remarks: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    family_details: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    person_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Submit household survey form with images"""
    
    # Verify volunteer exists
    volunteer = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    # TODO: Upload images to S3 (implement later)
    image_url = None
    person_image_url = None
    
    # Create form data
    form_data = FormData(
        volunteer_id=volunteer_id,
        household_name=household_name,
        address=address,
        colony=colony,
        family_members=family_members,
        voter_id=voter_id,
        aadhar=aadhar,
        gender=gender,
        knows_corporator=knows_corporator,
        satisfied_with_corporator=satisfied_with_corporator,
        knows_politician=knows_politician,
        supports_politician=supports_politician,
        politician_visit_freq=politician_visit_freq,
        services=services,
        service_frequency=service_frequency,
        service_satisfaction=service_satisfaction,
        attended_events=attended_events,
        income_range=income_range,
        main_occupation=main_occupation,
        education=education,
        housing_type=housing_type,
        children_count=children_count,
        visit_date=visit_date,
        volunteer_name=volunteer_name,
        corporator_division=corporator_division,
        zone=zone,
        remarks=remarks,
        latitude=latitude,
        longitude=longitude,
        image_url=image_url,
        person_image_url=person_image_url
    )
    
    db.add(form_data)
    db.flush()
    
    # Add family members
    if family_details:
        members = json.loads(family_details)
        for member in members:
            family_member = FamilyMember(
                form_data_id=form_data.id,
                name=member.get('name'),
                age=member.get('age'),
                gender=member.get('gender'),
                is_eligible_to_vote=member.get('isEligibleForVoting', False),
                voter_id=member.get('voter_id')
            )
            db.add(family_member)
    
    db.commit()
    db.refresh(form_data)
    
    return {"message": "Form submitted successfully ✅", "data": {"id": form_data.id}}


# ========================================
# DATA RETRIEVAL
# ========================================

@router.get("/formData/{volunteer_id}", response_model=List[FormDataResponse])
def get_volunteer_forms(
    volunteer_id: int,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    """Get all forms submitted by a volunteer"""
    query = db.query(FormData).filter(FormData.volunteer_id == volunteer_id)
    
    if from_date and to_date:
        query = query.filter(
            and_(
                func.date(FormData.visit_date) >= from_date,
                func.date(FormData.visit_date) <= to_date
            )
        )
    
    forms = query.order_by(FormData.created_at.desc()).all()
    return forms


@router.get("/map-pins", response_model=List[MapPinResponse])
def get_map_pins(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all form data with coordinates for map visualization"""
    
    # Get volunteers under current politician
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == current_user.user_id
    ).subquery()
    
    pins = db.query(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.latitude.isnot(None),
        FormData.longitude.isnot(None)
    ).order_by(FormData.visit_date.desc()).all()
    
    return pins


# ========================================
# DASHBOARD ANALYTICS
# ========================================

@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard summary statistics"""
    
    # Get volunteer IDs under current politician
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()
    volunteer_ids = [v[0] for v in volunteer_ids]
    
    total_households = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).scalar()
    
    total_voters = db.query(func.count(FamilyMember.member_id)).join(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).scalar()
    
    total_supporters = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.supports_politician == 'Yes'
    ).scalar()
    
    # Satisfaction count
    feedback = db.query(FormData.service_satisfaction).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).all()
    
    satisfaction_count = {
        "VerySatisfied": sum(1 for f in feedback if f[0] and 'Very' in f[0]),
        "Satisfied": sum(1 for f in feedback if f[0] and 'Satisfied' in f[0] and 'Very' not in f[0]),
        "Neutral": sum(1 for f in feedback if f[0] and 'Neutral' in f[0]),
        "Dissatisfied": sum(1 for f in feedback if f[0] and 'Dissatisfied' in f[0])
    }
    
    return {
        "total_households": total_households or 0,
        "total_voters": total_voters or 0,
        "total_supporters": total_supporters or 0,
        "satisfaction_count": satisfaction_count
    }


@router.get("/dashboard/voter-demographics", response_model=VoterDemographicsResponse)
def get_voter_demographics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get age and gender distribution"""
    
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == current_user.user_id
    ).subquery()
    
    members = db.query(FamilyMember).join(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).all()
    
    age_groups = {'Under 18': 0, '18-25': 0, '26-40': 0, '41-60': 0, '60+': 0}
    gender_distribution = {'Male': 0, 'Female': 0, 'Other': 0}
    
    for member in members:
        age = member.age or 0
        if age < 18:
            age_groups['Under 18'] += 1
        elif age <= 25:
            age_groups['18-25'] += 1
        elif age <= 40:
            age_groups['26-40'] += 1
        elif age <= 60:
            age_groups['41-60'] += 1
        else:
            age_groups['60+'] += 1
        
        gender = member.gender or 'Other'
        if gender in gender_distribution:
            gender_distribution[gender] += 1
        else:
            gender_distribution['Other'] += 1
    
    return {
        "age_groups": age_groups,
        "gender_distribution": gender_distribution
    }


@router.get("/dashboard/political-support", response_model=PoliticalSupportResponse)
def get_political_support(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get political support breakdown"""
    
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == current_user.user_id
    ).subquery()
    
    data = db.query(FormData.supports_politician).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).all()
    
    result = {'yes': 0, 'no': 0, 'neutral': 0}
    for item in data:
        val = (item[0] or '').lower()
        if val == 'yes':
            result['yes'] += 1
        elif val == 'no':
            result['no'] += 1
        else:
            result['neutral'] += 1
    
    return result
