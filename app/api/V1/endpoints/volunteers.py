from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional, List
from datetime import date, datetime

from app.db.session import get_db
from app.models.volunteer import Volunteer
from app.models.form_data import FormData
from app.models.family_member import FamilyMember
from app.models.user import User
from app.schemas.volunteer import VolunteerCreate, VolunteerResponse, VolunteerUpdate
from app.schemas.form_data import (
    FormDataCreate, FormDataResponse, MapPinResponse,
    DashboardSummaryResponse, VoterDemographicsResponse
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
        "new_password": new_password
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
    gender: Optional[str] = Form(None),
    voter_id: Optional[str] = Form(None),
    aadhar: Optional[str] = Form(None),
    voter_names: Optional[str] = Form(None),
    voter_ages: Optional[str] = Form(None),
    voter_relation: Optional[str] = Form(None),
    knows_corporator: Optional[bool] = Form(None),
    satisfied_with_corporator: Optional[bool] = Form(None),
    knows_politician: Optional[str] = Form(None),  # ✅ String
    supports_politician: Optional[str] = Form(None),
    politician_visit_freq: Optional[str] = Form(None),
    services: Optional[str] = Form(None),
    service_frequency: Optional[str] = Form(None),
    service_satisfaction: Optional[str] = Form(None),
    attended_events: Optional[bool] = Form(None),
    known_leaders: Optional[str] = Form(None),
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
    location_accuracy: Optional[float] = Form(None),
    family_details: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    person_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Submit household survey form with images"""
    
    print(f"\n{'='*60}")
    print(f"📝 FORM SUBMISSION")
    print(f"{'='*60}")
    print(f"Volunteer ID: {volunteer_id}")
    print(f"Household Name: {household_name}")
    print(f"Family Members Count: {family_members}")
    print(f"Family Details JSON: {family_details}")
    print(f"Services: {services}")
    print(f"Location: ({latitude}, {longitude})")
    print(f"Accuracy: {location_accuracy}m")
    print(f"Has House Image: {image is not None}")
    print(f"Has Person Image: {person_image is not None}")
    
    # Verify volunteer exists
    volunteer = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    # TODO: Upload images to S3/cloud storage
    image_url = None
    person_image_url = None
    
    if image:
        print(f"House Image: {image.filename}, Size: {image.size}")
    
    if person_image:
        print(f"Person Image: {person_image.filename}, Size: {person_image.size}")
    
    # Parse visit_date
    visit_date_obj = None
    if visit_date:
        try:
            visit_date_obj = datetime.strptime(visit_date, '%Y-%m-%d').date()
        except ValueError:
            visit_date_obj = datetime.now().date()
    else:
        visit_date_obj = datetime.now().date()
    
    # Create form data
    form_data = FormData(
        volunteer_id=volunteer_id,
        household_name=household_name,
        address=address,
        colony=colony,
        family_members=family_members,
        gender=gender,
        voter_id=voter_id,
        aadhar=aadhar,
        voter_names=voter_names,
        voter_ages=voter_ages,
        voter_relation=voter_relation,
        knows_corporator=knows_corporator,
        satisfied_with_corporator=satisfied_with_corporator,
        knows_politician=knows_politician,  # ✅ String
        supports_politician=supports_politician,
        politician_visit_freq=politician_visit_freq,
        services=services,
        service_frequency=service_frequency,
        service_satisfaction=service_satisfaction,
        attended_events=attended_events,
        known_leaders=known_leaders,
        income_range=income_range,
        main_occupation=main_occupation,
        education=education,
        housing_type=housing_type,
        children_count=children_count,
        visit_date=visit_date_obj,
        volunteer_name=volunteer_name,
        corporator_division=corporator_division,
        zone=zone,
        remarks=remarks,
        latitude=latitude,
        longitude=longitude,
        image_url=image_url,
        person_image_url=person_image_url
    )
    
    print(f"✅ Form data object created")
    
    try:
        db.add(form_data)
        db.flush()
        print(f"✅ Form data saved with ID: {form_data.id}")
        
        # Add family members from JSON
        if family_details:
            try:
                members = json.loads(family_details)
                print(f"📋 Processing {len(members)} family members")
                
                for idx, member in enumerate(members):
                    print(f"  Member {idx + 1}: {member}")
                    
                    family_member = FamilyMember(
                        form_data_id=form_data.id,
                        name=member.get('name', ''),
                        age=member.get('age', 0),
                        gender=member.get('gender', ''),
                        is_eligible_to_vote=member.get('isEligibleForVoting', False) or member.get('is_eligible_for_voting', False),
                        voter_id=member.get('voter_id') or member.get('voterId')
                    )
                    db.add(family_member)
                
                print(f"✅ Added {len(members)} family members")
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing error: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid family_details JSON: {str(e)}")
        
        db.commit()
        db.refresh(form_data)
        
        print(f"✅ Form submitted successfully!")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "message": "Form submitted successfully ✅",
            "data": {
                "id": form_data.id,
                "household_name": form_data.household_name,
                "family_members": family_members,
                "location": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "accuracy": location_accuracy
                }
            }
        }
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error saving form: {e}")
        print(f"{'='*60}\n")
        raise HTTPException(status_code=500, detail=f"Failed to save form: {str(e)}")


# ========================================
# DATA RETRIEVAL
# ========================================

@router.get("/formData/{volunteer_id}")
def get_volunteer_forms(
    volunteer_id: int,
    from_date: Optional[date] = Query(None, alias="from_date"),
    to_date: Optional[date] = Query(None, alias="to_date"),
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
    
    # Convert to list of dicts
    result = []
    for form in forms:
        form_dict = {
            'id': form.id,
            'volunteer_id': form.volunteer_id,
            'household_name': form.household_name,
            'address': form.address,
            'colony': form.colony,
            'voter_id': form.voter_id,
            'aadhar': form.aadhar,
            'voter_names': form.voter_names,
            'voter_ages': form.voter_ages,
            'voter_relation': form.voter_relation,
            'gender': form.gender,
            'knows_corporator': form.knows_corporator,
            'satisfied_with_corporator': form.satisfied_with_corporator,
            'knows_politician': form.knows_politician,
            'supports_politician': form.supports_politician,
            'services': form.services,
            'visit_date': str(form.visit_date) if form.visit_date else None,
            'latitude': float(form.latitude) if form.latitude else None,
            'longitude': float(form.longitude) if form.longitude else None,
            'created_at': form.created_at.isoformat() if form.created_at else None,
        }
        result.append(form_dict)
    
    return result


@router.get("/AllformData")
def get_all_forms(
    from_date: Optional[date] = Query(None, alias="fromDate"),
    to_date: Optional[date] = Query(None, alias="toDate"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all forms for admin/politician"""
    
    # Get volunteer IDs under current politician
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()
    volunteer_ids = [v[0] for v in volunteer_ids]
    
    if not volunteer_ids:
        return {"data": []}
    
    query = db.query(FormData).filter(FormData.volunteer_id.in_(volunteer_ids))
    
    if from_date and to_date:
        query = query.filter(
            and_(
                func.date(FormData.visit_date) >= from_date,
                func.date(FormData.visit_date) <= to_date
            )
        )
    
    forms = query.order_by(FormData.created_at.desc()).all()
    
    result = []
    for form in forms:
        form_dict = {
            'id': form.id,
            'volunteer_id': form.volunteer_id,
            'household_name': form.household_name,
            'address': form.address,
            'colony': form.colony,
            'voter_id': form.voter_id,
            'aadhar': form.aadhar,
            'voter_names': form.voter_names,
            'voter_ages': form.voter_ages,
            'voter_relation': form.voter_relation,
            'gender': form.gender,
            'knows_corporator': form.knows_corporator,
            'satisfied_with_corporator': form.satisfied_with_corporator,
            'knows_politician': form.knows_politician,
            'supports_politician': form.supports_politician,
            'services': form.services,
            'visit_date': str(form.visit_date) if form.visit_date else None,
            'latitude': float(form.latitude) if form.latitude else None,
            'longitude': float(form.longitude) if form.longitude else None,
            'created_at': form.created_at.isoformat() if form.created_at else None,
        }
        result.append(form_dict)
    
    return {"data": result}


@router.get("/map-pins", response_model=List[MapPinResponse])
def get_map_pins(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all form data with coordinates for map visualization"""
    
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
    
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()
    volunteer_ids = [v[0] for v in volunteer_ids]
    
    if not volunteer_ids:
        return {
            "total_households": 0,
            "total_voters": 0,
            "total_supporters": 0,
            "satisfaction_count": {
                "VerySatisfied": 0,
                "Satisfied": 0,
                "Neutral": 0,
                "Dissatisfied": 0
            }
        }
    
    total_households = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).scalar()
    
    total_voters = db.query(func.count(FamilyMember.member_id)).join(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FamilyMember.is_eligible_to_vote == True
    ).scalar()
    
    total_supporters = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.supports_politician.isnot(None),
        FormData.supports_politician != '',
        FormData.supports_politician != 'Others'
    ).scalar()
    
    feedback = db.query(FormData.service_satisfaction).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).all()
    
    satisfaction_count = {
        "VerySatisfied": sum(1 for f in feedback if f[0] and 'Very Satisfied' in f[0]),
        "Satisfied": sum(1 for f in feedback if f[0] and f[0] == 'Satisfied'),
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


@router.get("/dashboard/political-support")  # ✅ No response_model
def get_political_support(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get political support breakdown by party - returns dynamic dictionary"""
    
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()
    volunteer_ids = [v[0] for v in volunteer_ids]
    
    if not volunteer_ids:
        return {}
    
    data = db.query(
        FormData.supports_politician,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.supports_politician.isnot(None),
        FormData.supports_politician != ''
    ).group_by(FormData.supports_politician).all()
    
    # Convert to dictionary
    result = {}
    for party, count in data:
        if party:
            result[party] = count
    
    return result  # ✅ Returns plain dict: {"BRS": 1, "BJP": 2, ...}



@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard summary for all volunteers under politician"""
    
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()
    volunteer_ids = [v[0] for v in volunteer_ids]
    
    if not volunteer_ids:
        return {
            "total_households": 0,
            "total_voters": 0,
            "total_supporters": 0,
            "satisfaction_count": {
                "VerySatisfied": 0,
                "Satisfied": 0,
                "Neutral": 0,
                "Dissatisfied": 0
            }
        }
    
    total_households = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).scalar() or 0
    
    total_voters = db.query(func.count(FamilyMember.member_id)).join(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FamilyMember.is_eligible_to_vote == True
    ).scalar() or 0
    
    total_supporters = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.supports_politician.isnot(None),
        FormData.supports_politician != '',
        FormData.supports_politician != 'Others'
    ).scalar() or 0
    
    feedback = db.query(FormData.service_satisfaction).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).all()
    
    satisfaction_count = {
        "VerySatisfied": sum(1 for f in feedback if f[0] and 'Very Satisfied' in f[0]),
        "Satisfied": sum(1 for f in feedback if f[0] and f[0] == 'Satisfied'),
        "Neutral": sum(1 for f in feedback if f[0] and 'Neutral' in f[0]),
        "Dissatisfied": sum(1 for f in feedback if f[0] and 'Dissatisfied' in f[0])
    }
    
    return {
        "total_households": total_households,
        "total_voters": total_voters,
        "total_supporters": total_supporters,
        "satisfaction_count": satisfaction_count
    }


@router.get("/dashboard/voter-demographics", response_model=VoterDemographicsResponse)
def get_voter_demographics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get age and gender distribution for all volunteers"""
    
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


@router.get("/dashboard/political-support")
def get_political_support(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get political support breakdown by party"""
    
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()
    volunteer_ids = [v[0] for v in volunteer_ids]
    
    if not volunteer_ids:
        return {}
    
    data = db.query(
        FormData.supports_politician,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.supports_politician.isnot(None),
        FormData.supports_politician != ''
    ).group_by(FormData.supports_politician).all()
    
    result = {}
    for party, count in data:
        if party:
            result[party] = count
    
    return result


@router.get("/dashboard/service-feedback")
def get_service_feedback(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get service feedback and coverage statistics"""
    
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()
    volunteer_ids = [v[0] for v in volunteer_ids]
    
    if not volunteer_ids:
        return {
            "services_provided": {},
            "service_frequency": {},
            "satisfaction_levels": {}
        }
    
    # Services provided count
    services_data = db.query(FormData.services).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.services.isnot(None)
    ).all()
    
    services_count = {}
    for service_row in services_data:
        if service_row[0]:
            service_list = [s.strip() for s in service_row[0].split(',')]
            for service in service_list:
                if service:
                    services_count[service] = services_count.get(service, 0) + 1
    
    # Service frequency
    freq_data = db.query(
        FormData.service_frequency,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.service_frequency.isnot(None)
    ).group_by(FormData.service_frequency).all()
    
    frequency_count = {freq: count for freq, count in freq_data if freq}
    
    # Satisfaction levels
    satisfaction_data = db.query(
        FormData.service_satisfaction,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.service_satisfaction.isnot(None)
    ).group_by(FormData.service_satisfaction).all()
    
    satisfaction_count = {sat: count for sat, count in satisfaction_data if sat}
    
    return {
        "services_provided": services_count,
        "service_frequency": frequency_count,
        "satisfaction_levels": satisfaction_count
    }


@router.get("/dashboard/volunteer-overview")
def get_volunteer_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get overview of all volunteers and their performance"""
    
    volunteers = db.query(Volunteer).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()
    
    volunteer_stats = []
    
    for volunteer in volunteers:
        forms_count = db.query(func.count(FormData.id)).filter(
            FormData.volunteer_id == volunteer.id
        ).scalar() or 0
        
        voters_count = db.query(func.count(FamilyMember.member_id)).join(FormData).filter(
            FormData.volunteer_id == volunteer.id,
            FamilyMember.is_eligible_to_vote == True
        ).scalar() or 0
        
        last_submission = db.query(func.max(FormData.created_at)).filter(
            FormData.volunteer_id == volunteer.id
        ).scalar()
        
        volunteer_stats.append({
            "id": volunteer.id,
            "username": volunteer.username,
            "email": volunteer.email,
            "phone_number": volunteer.phone_number,
            "is_active": volunteer.is_active,
            "total_forms": forms_count,
            "total_voters": voters_count,
            "last_submission": last_submission.isoformat() if last_submission else None
        })
    
    return {
        "total_volunteers": len(volunteers),
        "active_volunteers": sum(1 for v in volunteers if v.is_active),
        "volunteers": volunteer_stats
    }


# ========================================
# INDIVIDUAL VOLUNTEER DASHBOARD
# ========================================

@router.get("/volunteer/dashboard/summary/{volunteer_id}")
def get_volunteer_dashboard_summary(
    volunteer_id: int,
    db: Session = Depends(get_db)
):
    """Get dashboard summary for a specific volunteer"""
    
    volunteer = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    total_households = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id == volunteer_id
    ).scalar() or 0
    
    total_voters = db.query(func.count(FamilyMember.member_id)).join(FormData).filter(
        FormData.volunteer_id == volunteer_id,
        FamilyMember.is_eligible_to_vote == True
    ).scalar() or 0
    
    total_supporters = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id == volunteer_id,
        FormData.supports_politician.isnot(None),
        FormData.supports_politician != '',
        FormData.supports_politician != 'Others'
    ).scalar() or 0
    
    feedback = db.query(FormData.service_satisfaction).filter(
        FormData.volunteer_id == volunteer_id
    ).all()
    
    satisfaction_count = {
        "VerySatisfied": sum(1 for f in feedback if f[0] and 'Very Satisfied' in f[0]),
        "Satisfied": sum(1 for f in feedback if f[0] and f[0] == 'Satisfied'),
        "Neutral": sum(1 for f in feedback if f[0] and 'Neutral' in f[0]),
        "Dissatisfied": sum(1 for f in feedback if f[0] and 'Dissatisfied' in f[0])
    }
    
    return {
        "total_households": total_households,
        "total_voters": total_voters,
        "total_supporters": total_supporters,
        "satisfaction_count": satisfaction_count
    }


@router.get("/volunteer/dashboard/voter-demographics/{volunteer_id}")
def get_volunteer_voter_demographics(
    volunteer_id: int,
    db: Session = Depends(get_db)
):
    """Get age and gender distribution for a specific volunteer"""
    
    members = db.query(FamilyMember).join(FormData).filter(
        FormData.volunteer_id == volunteer_id
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


@router.get("/volunteer/dashboard/political-support/{volunteer_id}")
def get_volunteer_political_support(
    volunteer_id: int,
    db: Session = Depends(get_db)
):
    """Get political support breakdown for a specific volunteer"""
    
    data = db.query(
        FormData.supports_politician,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id == volunteer_id,
        FormData.supports_politician.isnot(None),
        FormData.supports_politician != ''
    ).group_by(FormData.supports_politician).all()
    
    result = {}
    for party, count in data:
        if party:
            result[party] = count
    
    return result


@router.get("/volunteer/dashboard/service-feedback/{volunteer_id}")
def get_volunteer_service_feedback(
    volunteer_id: int,
    db: Session = Depends(get_db)
):
    """Get service feedback for a specific volunteer"""
    
    # Services provided count
    services_data = db.query(FormData.services).filter(
        FormData.volunteer_id == volunteer_id,
        FormData.services.isnot(None)
    ).all()
    
    services_count = {}
    for service_row in services_data:
        if service_row[0]:
            service_list = [s.strip() for s in service_row[0].split(',')]
            for service in service_list:
                if service:
                    services_count[service] = services_count.get(service, 0) + 1
    
    # Service frequency
    freq_data = db.query(
        FormData.service_frequency,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id == volunteer_id,
        FormData.service_frequency.isnot(None)
    ).group_by(FormData.service_frequency).all()
    
    frequency_count = {freq: count for freq, count in freq_data if freq}
    
    # Satisfaction levels
    satisfaction_data = db.query(
        FormData.service_satisfaction,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id == volunteer_id,
        FormData.service_satisfaction.isnot(None)
    ).group_by(FormData.service_satisfaction).all()
    
    satisfaction_count = {sat: count for sat, count in satisfaction_data if sat}
    
    return {
        "services_provided": services_count,
        "service_frequency": frequency_count,
        "satisfaction_levels": satisfaction_count
    }


@router.get("/volunteer/dashboard/volunteer-overview/{volunteer_id}")
def get_volunteer_overview_individual(
    volunteer_id: int,
    db: Session = Depends(get_db)
):
    """Get overview for a specific volunteer"""
    
    volunteer = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    forms_count = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id == volunteer_id
    ).scalar() or 0
    
    voters_count = db.query(func.count(FamilyMember.member_id)).join(FormData).filter(
        FormData.volunteer_id == volunteer_id,
        FamilyMember.is_eligible_to_vote == True
    ).scalar() or 0
    
    last_submission = db.query(func.max(FormData.created_at)).filter(
        FormData.volunteer_id == volunteer_id
    ).scalar()
    
    # Recent submissions
    recent_forms = db.query(FormData).filter(
        FormData.volunteer_id == volunteer_id
    ).order_by(FormData.created_at.desc()).limit(10).all()
    
    recent_submissions = []
    for form in recent_forms:
        recent_submissions.append({
            "id": form.id,
            "household_name": form.household_name,
            "address": form.address,
            "visit_date": str(form.visit_date) if form.visit_date else None,
            "created_at": form.created_at.isoformat() if form.created_at else None
        })
    
    return {
        "volunteer": {
            "id": volunteer.id,
            "username": volunteer.username,
            "email": volunteer.email,
            "phone_number": volunteer.phone_number,
            "is_active": volunteer.is_active
        },
        "total_forms": forms_count,
        "total_voters": voters_count,
        "last_submission": last_submission.isoformat() if last_submission else None,
        "recent_submissions": recent_submissions
    }