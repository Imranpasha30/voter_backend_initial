from fastapi import APIRouter, Depends, HTTPException, Query, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, distinct
from typing import Optional, List, Dict
from datetime import date, datetime, timedelta
import json

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
    
    existing = db.query(Volunteer).filter(Volunteer.email == volunteer.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_volunteer = Volunteer(
        politician_id=current_user.user_id,
        username=volunteer.username,
        email=volunteer.email,
        password=volunteer.password,
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
    
    volunteer.password = new_password
    db.commit()
    
    return {
        "message": "Password reset successfully",
        "email": volunteer.email,
        "new_password": new_password
    }


# ========================================
# FORM DATA SUBMISSION (NO IMAGES)
# ========================================
@router.post("/form", response_model=dict)
async def submit_form(
    volunteer_id: int = Form(...),
    
    # 1. Head of Family & Basic Info
    household_name: Optional[str] = Form(None),
    mobile_number: Optional[str] = Form(None),
    caste: Optional[str] = Form(None),
    religion: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    colony: Optional[str] = Form(None),
    area: Optional[str] = Form(None),
    family_members_count: Optional[int] = Form(0),  # Flutter sends this
    
    # ✅ HEAD OF FAMILY VOTER INFO (add these to Flutter later)
    voter_id: Optional[str] = Form(None),
    aadhar: Optional[str] = Form(None),
    voter_names: Optional[str] = Form(None),
    voter_ages: Optional[str] = Form(None),
    voter_relation: Optional[str] = Form(None),
    
    # 2. Political Influence
    knows_corporator: Optional[bool] = Form(None),
    corporator_name: Optional[str] = Form(None),
    other_politicians_known: Optional[str] = Form(None),  # Flutter sends this
    known_leaders: Optional[str] = Form(None),
    current_party_support: Optional[str] = Form(None),
    favourite_party: Optional[str] = Form(None),
    
    # 3. Services & Performance
    services_received: Optional[str] = Form(None),
    service_frequency: Optional[str] = Form(None),
    politician_visit_freq: Optional[str] = Form(None),
    satisfaction_with_corporator: Optional[str] = Form(None),
    satisfaction_with_service: Optional[str] = Form(None),
    service_satisfaction: Optional[str] = Form(None),
    
    # 4. Community Engagement
    attended_events: Optional[bool] = Form(None),
    work_done_in_ward: Optional[bool] = Form(None),
    work_details: Optional[str] = Form(None),
    
    # 5. Demographics
    income_range: Optional[str] = Form(None),
    main_occupation: Optional[str] = Form(None),
    highest_education: Optional[str] = Form(None),  # Flutter sends this
    housing_type: Optional[str] = Form(None),
    govt_schemes: Optional[str] = Form(None),
    children_count: Optional[int] = Form(0),
    
    # 6. Meta
    visit_date: Optional[str] = Form(None),
    volunteer_name: Optional[str] = Form(None),
    remarks: Optional[str] = Form(None),
    corporator_division: Optional[str] = Form(None),
    zone: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    location_accuracy: Optional[float] = Form(None),
    
    family_details: Optional[str] = Form(None),
    
    db: Session = Depends(get_db)
):
    """Submit household survey form"""
    
    print(f"\n{'='*60}")
    print(f"📝 FORM SUBMISSION")
    print(f"{'='*60}")
    
    volunteer = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    # Parse visit_date
    visit_date_obj = datetime.now().date()
    if visit_date:
        try:
            visit_date_obj = datetime.strptime(visit_date, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # ✅ Create form data with ALL columns mapped correctly
    form_data = FormData(
        volunteer_id=volunteer_id,
        
        # Section 1: Basic Info
        household_name=household_name,
        mobile_number=mobile_number,
        caste=caste,
        religion=religion,
        gender=gender,
        address=address,
        colony=colony,
        area=area,
        
        # ✅ Store in BOTH columns for compatibility
        family_members=family_members_count,
        family_members_count=family_members_count,
        
        # ✅ Head of Family Voter Info
        voter_id=voter_id,
        aadhar=aadhar,
        voter_names=voter_names,
        voter_ages=voter_ages,
        voter_relation=voter_relation,
        
        # Section 2: Political Influence
        knows_corporator=knows_corporator,
        corporator_name=corporator_name if knows_corporator else None,
        
        # ✅ Store in BOTH columns
        knows_politician=other_politicians_known,
        other_politicians_known=other_politicians_known,
        
        known_leaders=known_leaders,
        current_party_support=current_party_support,
        favourite_party=favourite_party,
        
        # Section 3: Services
        services_received=services_received,
        service_frequency=service_frequency,
        politician_visit_freq=politician_visit_freq,
        satisfaction_with_corporator=satisfaction_with_corporator,
        satisfaction_with_service=satisfaction_with_service,
        service_satisfaction=service_satisfaction,
        
        # Section 4: Community
        attended_events=attended_events,
        work_done_in_ward=work_done_in_ward,
        work_details=work_details if work_done_in_ward else None,
        
        # Section 5: Demographics
        income_range=income_range,
        main_occupation=main_occupation,
        
        # ✅ Store in BOTH columns
        education=highest_education,
        highest_education=highest_education,
        
        housing_type=housing_type,
        govt_schemes=govt_schemes,
        children_count=children_count,
        
        # Section 6: Meta
        visit_date=visit_date_obj,
        volunteer_name=volunteer_name,
        remarks=remarks,
        corporator_division=corporator_division,
        zone=zone,
        latitude=latitude,
        longitude=longitude,
        location_accuracy=location_accuracy
    )
    
    try:
        db.add(form_data)
        db.flush()
        print(f"✅ Form data saved with ID: {form_data.id}")
        
        # Add family members
        if family_details:
            try:
                members = json.loads(family_details)
                print(f"📋 Processing {len(members)} family members")
                
                for member in members:
                    family_member = FamilyMember(
                        form_data_id=form_data.id,
                        name=member.get('name', ''),
                        age=member.get('age', 0),
                        gender=member.get('gender', ''),
                        relation_to_head=member.get('relation', 'Other'),
                        voter_id=member.get('voterId', None),
                        aadhar_id=member.get('aadharId', None),
                        is_eligible_to_vote=member.get('isEligible', False)
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
                "family_members": family_members_count,
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
    
    result = []
    for form in forms:
        form_dict = {
            # Basic Info
            'id': form.id,
            'volunteer_id': form.volunteer_id,
            'household_name': form.household_name,
            'mobile_number': form.mobile_number,
            'caste': form.caste,
            'religion': form.religion,
            'gender': form.gender,
            'address': form.address,
            'colony': form.colony,
            'area': form.area,
            'family_members': form.family_members,  # ✅ Actual DB column
            
            # Voter Info
            'voter_id': form.voter_id,
            'aadhar': form.aadhar,
            'voter_names': form.voter_names,
            'voter_ages': form.voter_ages,
            'voter_relation': form.voter_relation,
            
            # Political Info
            'knows_corporator': form.knows_corporator,
            'corporator_name': form.corporator_name,
            'knows_politician': form.knows_politician,  # ✅ Actual DB column
            'known_leaders': form.known_leaders,  # ✅ Actual DB column
            'current_party_support': form.current_party_support,
            'favourite_party': form.favourite_party,
            
            # Services
            'services_received': form.services_received,
            'service_frequency': form.service_frequency,
            'politician_visit_freq': form.politician_visit_freq,
            'satisfaction_with_corporator': form.satisfaction_with_corporator,
            'satisfaction_with_service': form.satisfaction_with_service,
            'service_satisfaction': form.service_satisfaction,  # ✅ Actual DB column
            
            # Community
            'attended_events': form.attended_events,
            'work_done_in_ward': form.work_done_in_ward,
            'work_details': form.work_details,
            
            # Demographics
            'income_range': form.income_range,
            'main_occupation': form.main_occupation,
            'education': form.education,  # ✅ Actual DB column (not highest_education)
            'housing_type': form.housing_type,
            'govt_schemes': form.govt_schemes,
            'children_count': form.children_count,  # ✅ Actual DB column
            
            # Meta
            'visit_date': str(form.visit_date) if form.visit_date else None,
            'volunteer_name': form.volunteer_name,
            'remarks': form.remarks,
            'corporator_division': form.corporator_division,  # ✅ Actual DB column
            'zone': form.zone,  # ✅ Actual DB column
            
            # Media & Location
            'image_url': form.image_url,
            'person_image_url': form.person_image_url,
            'latitude': float(form.latitude) if form.latitude else None,
            'longitude': float(form.longitude) if form.longitude else None,
            'location_accuracy': float(form.location_accuracy) if form.location_accuracy else None,
            
            # Timestamps
            'created_at': form.created_at.isoformat() if form.created_at else None,
            'updated_at': form.updated_at.isoformat() if form.updated_at else None,
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
        result.append({
            'id': form.id,
            'household_name': form.household_name,
            'area': form.area,
            'caste': form.caste,
            'current_party_support': form.current_party_support,
            'visit_date': str(form.visit_date) if form.visit_date else None,
            'created_at': form.created_at.isoformat()
        })
    
    return {"data": result}


@router.get("/map-pins")
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

# ========================================
# HELPER FUNCTION - Get Volunteer IDs for Current Politician
# ========================================
def get_politician_volunteer_ids(politician_id: int, db: Session) -> List[int]:
    """Get all volunteer IDs belonging to the current politician"""
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == politician_id
    ).all()
    return [v[0] for v in volunteer_ids]


# ========================================
# 1. OVERVIEW DASHBOARD (Enhanced)
# ========================================
@router.get("/dashboard/overview")
def get_dashboard_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive overview statistics
    ✅ Data isolated per politician
    """
    volunteer_ids = get_politician_volunteer_ids(current_user.user_id, db)
    
    if not volunteer_ids:
        return {
            "total_households": 0,
            "total_family_members": 0,
            "total_eligible_voters": 0,
            "total_volunteers": 0,
            "active_volunteers": 0,
            "surveys_today": 0,
            "surveys_this_week": 0,
            "surveys_this_month": 0,
            "avg_family_size": 0,
            "data_completeness": 0
        }
    
    # Basic counts
    total_households = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).scalar() or 0
    
    total_family_members = db.query(func.count(FamilyMember.member_id)).join(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).scalar() or 0
    
    total_eligible_voters = db.query(func.count(FamilyMember.member_id)).join(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FamilyMember.is_eligible_to_vote == True
    ).scalar() or 0
    
    # Volunteer stats
    total_volunteers = db.query(func.count(Volunteer.id)).filter(
        Volunteer.politician_id == current_user.user_id
    ).scalar() or 0
    
    active_volunteers = db.query(func.count(Volunteer.id)).filter(
        Volunteer.politician_id == current_user.user_id,
        Volunteer.is_active == True
    ).scalar() or 0
    
    # Time-based surveys
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    surveys_today = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        func.date(FormData.created_at) == today
    ).scalar() or 0
    
    surveys_this_week = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        func.date(FormData.created_at) >= week_ago
    ).scalar() or 0
    
    surveys_this_month = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        func.date(FormData.created_at) >= month_ago
    ).scalar() or 0
    
    # Average family size
    avg_family_size = db.query(func.avg(FormData.family_members_count)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.family_members_count.isnot(None)
    ).scalar() or 0
    
    # Data completeness (surveys with GPS coordinates)
    surveys_with_gps = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.latitude.isnot(None),
        FormData.longitude.isnot(None)
    ).scalar() or 0
    
    data_completeness = (surveys_with_gps / total_households * 100) if total_households > 0 else 0
    
    return {
        "total_households": total_households,
        "total_family_members": total_family_members,
        "total_eligible_voters": total_eligible_voters,
        "total_volunteers": total_volunteers,
        "active_volunteers": active_volunteers,
        "surveys_today": surveys_today,
        "surveys_this_week": surveys_this_week,
        "surveys_this_month": surveys_this_month,
        "avg_family_size": round(float(avg_family_size), 2),
        "data_completeness": round(data_completeness, 2)
    }


# ========================================
# 2. DEMOGRAPHIC ANALYTICS
# ========================================
@router.get("/dashboard/demographics")
def get_demographics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive demographic breakdown
    ✅ Data isolated per politician
    """
    volunteer_ids = get_politician_volunteer_ids(current_user.user_id, db)
    
    if not volunteer_ids:
        return {
            "age_distribution": {},
            "gender_distribution": {},
            "caste_distribution": {},
            "religion_distribution": {},
            "education_distribution": {},
            "income_distribution": {},
            "occupation_distribution": {},
            "housing_distribution": {}
        }
    
    # Age Distribution (from family members)
    members = db.query(FamilyMember.age).join(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FamilyMember.age.isnot(None)
    ).all()
    
    age_distribution = {
        'Children (0-17)': 0,
        'Young Adults (18-25)': 0,
        'Adults (26-40)': 0,
        'Middle Age (41-60)': 0,
        'Senior Citizens (60+)': 0
    }
    
    for (age,) in members:
        if age < 18:
            age_distribution['Children (0-17)'] += 1
        elif age <= 25:
            age_distribution['Young Adults (18-25)'] += 1
        elif age <= 40:
            age_distribution['Adults (26-40)'] += 1
        elif age <= 60:
            age_distribution['Middle Age (41-60)'] += 1
        else:
            age_distribution['Senior Citizens (60+)'] += 1
    
    # Gender Distribution
    gender_data = db.query(
        FamilyMember.gender,
        func.count(FamilyMember.member_id)
    ).join(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FamilyMember.gender.isnot(None)
    ).group_by(FamilyMember.gender).all()
    
    gender_distribution = {gender: count for gender, count in gender_data if gender}
    
    # Caste Distribution
    caste_data = db.query(
        FormData.caste,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.caste.isnot(None)
    ).group_by(FormData.caste).all()
    
    caste_distribution = {caste: count for caste, count in caste_data if caste}
    
    # Religion Distribution
    religion_data = db.query(
        FormData.religion,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.religion.isnot(None)
    ).group_by(FormData.religion).all()
    
    religion_distribution = {religion: count for religion, count in religion_data if religion}
    
    # Education Distribution
    education_data = db.query(
        FormData.highest_education,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.highest_education.isnot(None)
    ).group_by(FormData.highest_education).all()
    
    education_distribution = {edu: count for edu, count in education_data if edu}
    
    # Income Distribution
    income_data = db.query(
        FormData.income_range,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.income_range.isnot(None)
    ).group_by(FormData.income_range).all()
    
    income_distribution = {income: count for income, count in income_data if income}
    
    # Occupation Distribution
    occupation_data = db.query(
        FormData.main_occupation,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.main_occupation.isnot(None)
    ).group_by(FormData.main_occupation).all()
    
    occupation_distribution = {occ: count for occ, count in occupation_data if occ}
    
    # Housing Distribution
    housing_data = db.query(
        FormData.housing_type,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.housing_type.isnot(None)
    ).group_by(FormData.housing_type).all()
    
    housing_distribution = {house: count for house, count in housing_data if house}
    
    return {
        "age_distribution": age_distribution,
        "gender_distribution": gender_distribution,
        "caste_distribution": caste_distribution,
        "religion_distribution": religion_distribution,
        "education_distribution": education_distribution,
        "income_distribution": income_distribution,
        "occupation_distribution": occupation_distribution,
        "housing_distribution": housing_distribution
    }


# ========================================
# 3. POLITICAL ANALYTICS (Enhanced)
# ========================================
@router.get("/dashboard/political-insights")
def get_political_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive political analysis
    ✅ Data isolated per politician
    """
    volunteer_ids = get_politician_volunteer_ids(current_user.user_id, db)
    
    if not volunteer_ids:
        return {
            "party_support": {},
            "favourite_party": {},
            "corporator_recognition": {},
            "political_engagement": {},
            "win_probability": {}
        }
    
    # Current Party Support
    party_support_data = db.query(
        FormData.current_party_support,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.current_party_support.isnot(None),
        FormData.current_party_support != ''
    ).group_by(FormData.current_party_support).all()
    
    party_support = {party: count for party, count in party_support_data if party}
    
    # Favourite Party
    favourite_party_data = db.query(
        FormData.favourite_party,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.favourite_party.isnot(None),
        FormData.favourite_party != ''
    ).group_by(FormData.favourite_party).all()
    
    favourite_party = {party: count for party, count in favourite_party_data if party}
    
    # Corporator Recognition
    knows_corporator = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.knows_corporator == True
    ).scalar() or 0
    
    total_surveys = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).scalar() or 1
    
    corporator_recognition = {
        "knows_corporator": knows_corporator,
        "does_not_know": total_surveys - knows_corporator,
        "recognition_rate": round((knows_corporator / total_surveys * 100), 2)
    }
    
    # Political Engagement
    attended_events = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.attended_events == True
    ).scalar() or 0
    
    aware_of_work = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.work_done_in_ward == True
    ).scalar() or 0
    
    political_engagement = {
        "attended_events": attended_events,
        "not_attended": total_surveys - attended_events,
        "aware_of_work_done": aware_of_work,
        "engagement_rate": round((attended_events / total_surveys * 100), 2)
    }
    
    # Win Probability Insights
    # TODO: Add your party name here
    your_party = "YourPartyName"  # Change this
    
    strong_supporters = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.current_party_support == your_party,
        FormData.favourite_party == your_party
    ).scalar() or 0
    
    potential_supporters = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.favourite_party == your_party
    ).scalar() or 0
    
    swing_voters = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.current_party_support != FormData.favourite_party,
        FormData.satisfaction_with_service == 'Moderate'
    ).scalar() or 0
    
    win_probability = {
        "strong_supporters": strong_supporters,
        "potential_supporters": potential_supporters,
        "swing_voters": swing_voters,
        "total_reachable": strong_supporters + potential_supporters + swing_voters
    }
    
    return {
        "party_support": party_support,
        "favourite_party": favourite_party,
        "corporator_recognition": corporator_recognition,
        "political_engagement": political_engagement,
        "win_probability": win_probability
    }


# ========================================
# 4. GEOGRAPHIC ANALYTICS
# ========================================
@router.get("/dashboard/geographic")
def get_geographic_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get area/zone-wise distribution
    ✅ Data isolated per politician
    """
    volunteer_ids = get_politician_volunteer_ids(current_user.user_id, db)
    
    if not volunteer_ids:
        return {
            "by_area": {},
            "by_zone": {},
            "by_colony": {},
            "coverage_map": []
        }
    
    # Area-wise distribution
    area_data = db.query(
        FormData.area,
        func.count(FormData.id).label('households'),
        func.count(FamilyMember.member_id).label('voters')
    ).outerjoin(FamilyMember).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.area.isnot(None)
    ).group_by(FormData.area).all()
    
    by_area = {
        area: {"households": households, "voters": voters if voters else 0}
        for area, households, voters in area_data if area
    }
    
    # Zone-wise distribution
    zone_data = db.query(
        FormData.zone,
        func.count(FormData.id).label('households')
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.zone.isnot(None)
    ).group_by(FormData.zone).all()
    
    by_zone = {zone: households for zone, households in zone_data if zone}
    
    # Colony-wise distribution
    colony_data = db.query(
        FormData.colony,
        func.count(FormData.id).label('households')
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.colony.isnot(None)
    ).group_by(FormData.colony).all()
    
    by_colony = {colony: households for colony, households in colony_data if colony}
    
    # Coverage map (areas with coordinates)
    coverage_data = db.query(
        FormData.area,
        func.avg(FormData.latitude).label('avg_lat'),
        func.avg(FormData.longitude).label('avg_lng'),
        func.count(FormData.id).label('count')
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.latitude.isnot(None),
        FormData.longitude.isnot(None),
        FormData.area.isnot(None)
    ).group_by(FormData.area).all()
    
    coverage_map = [
        {
            "area": area,
            "latitude": float(avg_lat),
            "longitude": float(avg_lng),
            "survey_count": count
        }
        for area, avg_lat, avg_lng, count in coverage_data if area
    ]
    
    return {
        "by_area": by_area,
        "by_zone": by_zone,
        "by_colony": by_colony,
        "coverage_map": coverage_map
    }


# ========================================
# 5. SERVICE ANALYTICS (Enhanced)
# ========================================
@router.get("/dashboard/services")
def get_service_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get service distribution and satisfaction
    ✅ Data isolated per politician
    """
    volunteer_ids = get_politician_volunteer_ids(current_user.user_id, db)
    
    if not volunteer_ids:
        return {
            "services_provided": {},
            "satisfaction_levels": {},
            "service_frequency": {},
            "govt_schemes": {}
        }
    
    # Services provided (split comma-separated values)
    services_data = db.query(FormData.services_received).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.services_received.isnot(None)
    ).all()
    
    services_count = {}
    for (services,) in services_data:
        if services:
            service_list = [s.strip() for s in services.split(',')]
            for service in service_list:
                if service:
                    services_count[service] = services_count.get(service, 0) + 1
    
    # Satisfaction levels
    satisfaction_data = db.query(
        FormData.satisfaction_with_service,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.satisfaction_with_service.isnot(None)
    ).group_by(FormData.satisfaction_with_service).all()
    
    satisfaction_levels = {sat: count for sat, count in satisfaction_data if sat}
    
    # Service frequency
    frequency_data = db.query(
        FormData.service_frequency,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.service_frequency.isnot(None)
    ).group_by(FormData.service_frequency).all()
    
    service_frequency = {freq: count for freq, count in frequency_data if freq}
    
    # Government schemes
    schemes_data = db.query(FormData.govt_schemes).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.govt_schemes.isnot(None)
    ).all()
    
    schemes_count = {}
    for (schemes,) in schemes_data:
        if schemes:
            scheme_list = [s.strip() for s in schemes.split(',')]
            for scheme in scheme_list:
                if scheme:
                    schemes_count[scheme] = schemes_count.get(scheme, 0) + 1
    
    return {
        "services_provided": services_count,
        "satisfaction_levels": satisfaction_levels,
        "service_frequency": service_frequency,
        "govt_schemes": schemes_count
    }


# ========================================
# 6. VOLUNTEER PERFORMANCE (Enhanced)
# ========================================
@router.get("/dashboard/volunteer-performance")
def get_volunteer_performance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed volunteer performance metrics
    ✅ Data isolated per politician
    """
    volunteers = db.query(Volunteer).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()
    
    volunteer_stats = []
    
    for volunteer in volunteers:
        # Basic counts
        forms_count = db.query(func.count(FormData.id)).filter(
            FormData.volunteer_id == volunteer.id
        ).scalar() or 0
        
        voters_count = db.query(func.count(FamilyMember.member_id)).join(FormData).filter(
            FormData.volunteer_id == volunteer.id,
            FamilyMember.is_eligible_to_vote == True
        ).scalar() or 0
        
        # Last submission
        last_submission = db.query(func.max(FormData.created_at)).filter(
            FormData.volunteer_id == volunteer.id
        ).scalar()
        
        # Data quality score (% with GPS + photos)
        surveys_with_gps = db.query(func.count(FormData.id)).filter(
            FormData.volunteer_id == volunteer.id,
            FormData.latitude.isnot(None),
            FormData.longitude.isnot(None)
        ).scalar() or 0
        
        data_quality = (surveys_with_gps / forms_count * 100) if forms_count > 0 else 0
        
        # Areas covered
        areas_covered = db.query(func.count(func.distinct(FormData.area))).filter(
            FormData.volunteer_id == volunteer.id,
            FormData.area.isnot(None)
        ).scalar() or 0
        
        volunteer_stats.append({
            "id": volunteer.id,
            "username": volunteer.username,
            "email": volunteer.email,
            "phone_number": volunteer.phone_number,
            "is_active": volunteer.is_active,
            "total_surveys": forms_count,
            "total_voters": voters_count,
            "data_quality_score": round(data_quality, 2),
            "areas_covered": areas_covered,
            "last_submission": last_submission.isoformat() if last_submission else None
        })
    
    # Sort by total surveys (descending)
    volunteer_stats.sort(key=lambda x: x['total_surveys'], reverse=True)
    
    return {
        "total_volunteers": len(volunteers),
        "active_volunteers": sum(1 for v in volunteers if v.is_active),
        "volunteers": volunteer_stats
    }


# ========================================
# 7. TIME-BASED TRENDS
# ========================================
@router.get("/dashboard/trends")
def get_time_trends(
    current_user: User = Depends(get_current_user),
    days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db)
):
    """
    Get survey trends over time
    ✅ Data isolated per politician
    """
    volunteer_ids = get_politician_volunteer_ids(current_user.user_id, db)
    
    if not volunteer_ids:
        return {"daily_surveys": [], "weekly_surveys": []}
    
    # Daily survey count for last N days
    start_date = datetime.now().date() - timedelta(days=days)
    
    daily_data = db.query(
        func.date(FormData.created_at).label('date'),
        func.count(FormData.id).label('count')
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        func.date(FormData.created_at) >= start_date
    ).group_by(func.date(FormData.created_at)).order_by('date').all()
    
    daily_surveys = [
        {"date": str(date), "count": count}
        for date, count in daily_data
    ]
    
    return {
        "daily_surveys": daily_surveys,
        "period_days": days
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
        FormData.current_party_support.isnot(None),
        FormData.current_party_support != ''
    ).scalar() or 0
    
    feedback = db.query(FormData.satisfaction_with_service).filter(
        FormData.volunteer_id == volunteer_id
    ).all()
    
    satisfaction_count = {
        "VerySatisfied": sum(1 for f in feedback if f[0] == 'Yes'),
        "Satisfied": sum(1 for f in feedback if f[0] == 'Moderate'),
        "Neutral": 0,
        "Dissatisfied": sum(1 for f in feedback if f[0] == 'No')
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
        if age < 18: age_groups['Under 18'] += 1
        elif age <= 25: age_groups['18-25'] += 1
        elif age <= 40: age_groups['26-40'] += 1
        elif age <= 60: age_groups['41-60'] += 1
        else: age_groups['60+'] += 1
        
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
        FormData.current_party_support,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id == volunteer_id,
        FormData.current_party_support.isnot(None),
        FormData.current_party_support != ''
    ).group_by(FormData.current_party_support).all()
    
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
    
    services_data = db.query(FormData.services_received).filter(
        FormData.volunteer_id == volunteer_id,
        FormData.services_received.isnot(None)
    ).all()
    
    services_count = {}
    for service_row in services_data:
        if service_row[0]:
            service_list = [s.strip() for s in service_row[0].split(',')]
            for service in service_list:
                if service:
                    services_count[service] = services_count.get(service, 0) + 1
    
    satisfaction_data = db.query(
        FormData.satisfaction_with_service,
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id == volunteer_id,
        FormData.satisfaction_with_service.isnot(None)
    ).group_by(FormData.satisfaction_with_service).all()
    
    satisfaction_count = {sat: count for sat, count in satisfaction_data if sat}
    
    return {
        "services_provided": services_count,
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
