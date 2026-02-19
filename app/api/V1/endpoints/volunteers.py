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
from app.models.voter import Voter
from app.schemas.volunteer import VolunteerCreate, VolunteerResponse, VolunteerUpdate
from app.schemas.form_data import (
    FormDataCreate, FormDataResponse, MapPinResponse,
    DashboardSummaryResponse, VoterDemographicsResponse
)
# ✅ get_current_user           → politician-only endpoints (manage volunteers)
# ✅ get_politician_id_from_token → endpoints callable by BOTH politician & volunteer
from app.api.deps import get_current_user
from app.core.security import get_politician_id_from_token
from app.models.area import Area
from app.models.part import Part
from app.models.user_area import UserArea
from app.api.deps import get_current_user

router = APIRouter()


# ========================================
# VOLUNTEER MANAGEMENT (politician only)
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
        phone_number=volunteer.mobile_number,  # ✅ schema field → model column
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
    return db.query(Volunteer).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()


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
    if volunteer_update.mobile_number:
        volunteer.phone_number = volunteer_update.mobile_number  # ✅ fixed: was volunteer.mobile_number
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
    """Reset volunteer password"""
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
# VOTER SURVEY VALIDATION (volunteer auth)
# ========================================

def get_assigned_voter(db: Session, voter_id: str, caller_id: int, is_volunteer: bool = False):
    """
    Scoped voter lookup through assignment chain:
    UserArea → Area → Part → Voter
    - Volunteer: resolves politician_id first, then same chain
    - Politician: uses user_id directly
    """
    if is_volunteer:
        volunteer = db.query(Volunteer).filter(Volunteer.id == caller_id).first()
        if not volunteer:
            return None
        lookup_user_id = volunteer.politician_id
    else:
        lookup_user_id = caller_id

    return (
        db.query(Voter)
        .join(Part, Part.part_id == Voter.part_id)
        .join(Area, Area.area_id == Part.area_id)
        .join(UserArea, UserArea.area_id == Area.area_id)
        .filter(
            UserArea.user_id == lookup_user_id,
            Voter.epic_no == voter_id,
        )
        .first()
    )


@router.get("/check-voter-survey/{voter_id}")
def check_voter_survey_status(
    voter_id: str,
    db: Session = Depends(get_db),
    current_volunteer: Volunteer = Depends(get_current_user),  # ✅ returns Volunteer ORM object
):
    """Check if a voter ID already has a survey, scoped to assigned areas only."""
    voter_id = voter_id.strip().upper()

    # current_volunteer is a Volunteer ORM object — access attributes directly
    voter = get_assigned_voter(db, voter_id, caller_id=current_volunteer.id, is_volunteer=True)

    if not voter:
        return {
            "exists": False, "is_surveyed": False, "form_id": None,
            "message": f"Voter ID {voter_id} not found in your assigned area"
        }

    if voter.form_id:
        form = db.query(FormData).filter(FormData.id == voter.form_id).first()
        return {
            "exists": True, "is_surveyed": True, "form_id": voter.form_id,
            "household_name": form.household_name if form else None,
            "survey_date": str(form.visit_date) if form and form.visit_date else None,
            "message": f"⚠️ Voter {voter_id} already has a survey (Form #{voter.form_id})"
        }

    return {
        "exists": True, "is_surveyed": False, "form_id": None,
        "message": f"✅ Voter {voter_id} found. No survey yet."
    }


@router.post("/check-multiple-voters")
def check_multiple_voter_surveys(
    voter_ids: List[str],
    db: Session = Depends(get_db),
    current_volunteer: Volunteer = Depends(get_current_user),  # ✅ Volunteer ORM object
):
    """Check survey status for multiple voter IDs, scoped to assigned areas only."""
    results = []

    for raw_voter_id in voter_ids:
        if not raw_voter_id or not raw_voter_id.strip():
            continue

        voter_id = raw_voter_id.strip().upper()
        voter = get_assigned_voter(db, voter_id, caller_id=current_volunteer.id, is_volunteer=True)

        if not voter:
            results.append({
                "voter_id": voter_id, "exists": False,
                "is_surveyed": False, "message": "Not found in your assigned area"
            })
        elif voter.form_id:
            form = db.query(FormData).filter(FormData.id == voter.form_id).first()
            results.append({
                "voter_id": voter_id, "exists": True, "is_surveyed": True,
                "form_id": voter.form_id,
                "household_name": form.household_name if form else None,
                "message": f"Already surveyed (Form #{voter.form_id})"
            })
        else:
            results.append({
                "voter_id": voter_id, "exists": True,
                "is_surveyed": False, "message": "Available for survey"
            })

    return {
        "total_checked": len(voter_ids),
        "results": results,
        "duplicates_found": sum(1 for r in results if r.get("is_surveyed", False))
    }


# ========================================
# FORM SUBMISSION
# ========================================

@router.post("/form", response_model=dict)
async def submit_form(
    volunteer_id: int = Form(...),
    household_name: Optional[str] = Form(None),
    mobile_number: Optional[str] = Form(None),
    caste: Optional[str] = Form(None),
    religion: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    colony: Optional[str] = Form(None),
    area: Optional[str] = Form(None),
    family_members_count: Optional[int] = Form(0),
    voter_id: Optional[str] = Form(None),
    aadhar: Optional[str] = Form(None),
    voter_names: Optional[str] = Form(None),
    voter_ages: Optional[str] = Form(None),
    voter_relation: Optional[str] = Form(None),
    knows_corporator: Optional[bool] = Form(None),
    corporator_name: Optional[str] = Form(None),
    other_politicians_known: Optional[str] = Form(None),
    current_party_support: Optional[str] = Form(None),
    favourite_party: Optional[str] = Form(None),
    services_received: Optional[str] = Form(None),
    service_frequency: Optional[str] = Form(None),
    politician_visit_freq: Optional[str] = Form(None),
    satisfaction_with_corporator: Optional[str] = Form(None),
    satisfaction_with_service: Optional[str] = Form(None),
    attended_events: Optional[bool] = Form(None),
    work_done_in_ward: Optional[bool] = Form(None),
    work_details: Optional[str] = Form(None),
    income_range: Optional[str] = Form(None),
    main_occupation: Optional[str] = Form(None),
    highest_education: Optional[str] = Form(None),
    housing_type: Optional[str] = Form(None),
    govt_schemes: Optional[str] = Form(None),
    children_count: Optional[int] = Form(0),
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
    """Submit household survey form with voter tracking"""

    print(f"\n{'='*60}")
    print(f"📝 FORM SUBMISSION WITH VOTER TRACKING")
    print(f"{'='*60}")

    if voter_id:
        voter_id = voter_id.strip().upper()

    print(f"voter_id (normalized): {voter_id}")

    volunteer = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    # ✅ Block if head voter already surveyed
    if voter_id and voter_id.strip():
        head_voter = db.query(Voter).filter(Voter.epic_no == voter_id).first()
        if head_voter and head_voter.form_id:
            existing_form = db.query(FormData).filter(FormData.id == head_voter.form_id).first()
            raise HTTPException(
                status_code=400,
                detail=f"⚠️ Voter {voter_id} already has a survey "
                       f"(Form #{head_voter.form_id}, "
                       f"Household: {existing_form.household_name if existing_form else 'N/A'})"
            )

    visit_date_obj = datetime.now().date()
    if visit_date:
        try:
            visit_date_obj = datetime.strptime(visit_date, '%Y-%m-%d').date()
        except ValueError:
            pass

    form_data = FormData(
        volunteer_id=volunteer_id,
        household_name=household_name,
        mobile_number=mobile_number,
        caste=caste,
        religion=religion,
        gender=gender,
        address=address,
        colony=colony,
        area=area,
        family_members=family_members_count,
        family_members_count=family_members_count,
        voter_id=voter_id,
        aadhar=aadhar,
        voter_names=voter_names,
        voter_ages=voter_ages,
        voter_relation=voter_relation,
        knows_corporator=knows_corporator,
        corporator_name=corporator_name if knows_corporator else None,
        knows_politician=other_politicians_known,
        other_politicians_known=other_politicians_known,
        current_party_support=current_party_support,
        favourite_party=favourite_party,
        services_received=services_received,
        service_frequency=service_frequency,
        politician_visit_freq=politician_visit_freq,
        satisfaction_with_corporator=satisfaction_with_corporator,
        satisfaction_with_service=satisfaction_with_service,
        attended_events=attended_events,
        work_done_in_ward=work_done_in_ward,
        work_details=work_details if work_done_in_ward else None,
        income_range=income_range,
        main_occupation=main_occupation,
        education=highest_education,
        highest_education=highest_education,
        housing_type=housing_type,
        govt_schemes=govt_schemes,
        children_count=children_count,
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

        print(f"✅ Form saved with ID: {form_data.id}")

        voters_linked_count = 0

        if voter_id and voter_id.strip():
            head_voter = db.query(Voter).filter(Voter.epic_no == voter_id).first()
            if head_voter:
                head_voter.form_id = form_data.id
                head_voter.is_surveyed = True
                head_voter.survey_date = datetime.now()
                voters_linked_count += 1
                print(f"✅ Linked head voter {voter_id} → form {form_data.id}")
            else:
                print(f"ℹ️ Head voter {voter_id} not in voters table")

        surveyed_family_voters = []

        if family_details:
            try:
                members = json.loads(family_details)
                print(f"📋 Processing {len(members)} family members")

                for member in members:
                    raw_member_voter_id = member.get('voterId', None)
                    member_voter_id = (
                        raw_member_voter_id.strip().upper()
                        if raw_member_voter_id and raw_member_voter_id.strip()
                        else None
                    )

                    if member_voter_id:
                        existing_voter = db.query(Voter).filter(
                            Voter.epic_no == member_voter_id
                        ).first()

                        if existing_voter and existing_voter.form_id and \
                                existing_voter.form_id != form_data.id:
                            db.rollback()
                            raise HTTPException(
                                status_code=400,
                                detail=f"⚠️ Family member voter ID {member_voter_id} "
                                       f"already has a survey (Form #{existing_voter.form_id})"
                            )

                        if existing_voter:
                            surveyed_family_voters.append(member_voter_id)

                    db.add(FamilyMember(
                        form_data_id=form_data.id,
                        name=member.get('name', ''),
                        age=member.get('age', 0),
                        gender=member.get('gender', ''),
                        relation_to_head=member.get('relation', 'Other'),
                        voter_id=member_voter_id,
                        aadhar_id=member.get('aadharId', None),
                        is_eligible_to_vote=member.get('isEligible', False),
                        is_voter_verified=bool(member_voter_id)
                    ))

                print(f"✅ Added {len(members)} family members")

                for fv_id in surveyed_family_voters:
                    voter = db.query(Voter).filter(Voter.epic_no == fv_id).first()
                    if voter:
                        voter.form_id = form_data.id
                        voter.is_surveyed = True
                        voter.survey_date = datetime.now()
                        voters_linked_count += 1

                if surveyed_family_voters:
                    print(f"✅ Linked {len(surveyed_family_voters)} family voters → form {form_data.id}")

            except json.JSONDecodeError as e:
                print(f"❌ JSON error: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid family_details JSON: {str(e)}")

        db.commit()
        db.refresh(form_data)

        print(f"🎉 Form submitted! Voters linked: {voters_linked_count}")
        print(f"{'='*60}\n")

        return {
            "success": True,
            "message": "Form submitted successfully ✅",
            "data": {
                "id": form_data.id,
                "household_name": form_data.household_name,
                "family_members": family_members_count,
                "voters_linked": voters_linked_count,
                "location": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "accuracy": location_accuracy
                }
            }
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save form: {str(e)}")


# ========================================
# FORM DETAIL — View Survey Button
# ========================================

@router.get("/form/{form_id}")
def get_form_detail(
    form_id: int,
    politician_id: int = Depends(get_politician_id_from_token),
    db: Session = Depends(get_db)
):
    """Get full survey form detail by form_id. Access controlled by politician chain."""
    form = db.query(FormData).join(Volunteer).filter(
        FormData.id == form_id,
        Volunteer.politician_id == politician_id
    ).first()

    if not form:
        raise HTTPException(status_code=404, detail="Survey form not found or access denied")

    family_members = db.query(FamilyMember).filter(
        FamilyMember.form_data_id == form_id
    ).all()

    linked_voters = db.query(Voter).filter(
        Voter.form_id == form_id
    ).all()

    return {
        "form_id": form.id,
        "household_name": form.household_name,
        "mobile_number": form.mobile_number,
        "address": form.address,
        "colony": form.colony,
        "area": form.area,
        "caste": form.caste,
        "religion": form.religion,
        "gender": form.gender,
        "family_members_count": form.family_members_count,
        "knows_corporator": form.knows_corporator,
        "corporator_name": form.corporator_name,
        "current_party_support": form.current_party_support,
        "favourite_party": form.favourite_party,
        "other_politicians_known": form.other_politicians_known,
        "services_received": form.services_received,
        "service_frequency": form.service_frequency,
        "satisfaction_with_corporator": form.satisfaction_with_corporator,
        "satisfaction_with_service": form.satisfaction_with_service,
        "politician_visit_freq": form.politician_visit_freq,
        "attended_events": form.attended_events,
        "work_done_in_ward": form.work_done_in_ward,
        "work_details": form.work_details,
        "income_range": form.income_range,
        "main_occupation": form.main_occupation,
        "highest_education": form.highest_education,
        "housing_type": form.housing_type,
        "govt_schemes": form.govt_schemes,
        "children_count": form.children_count,
        "visit_date": str(form.visit_date) if form.visit_date else None,
        "volunteer_name": form.volunteer_name,
        "remarks": form.remarks,
        "corporator_division": form.corporator_division,
        "zone": form.zone,
        "is_voted": form.is_voted,
        "voting_status": form.voting_status,
        "latitude": float(form.latitude) if form.latitude else None,
        "longitude": float(form.longitude) if form.longitude else None,
        "image_url": form.image_url,
        "person_image_url": form.person_image_url,
        "created_at": form.created_at.isoformat() if form.created_at else None,
        "family_members": [
            {
                "member_id": m.member_id,
                "name": m.name,
                "age": m.age,
                "gender": m.gender,
                "relation_to_head": m.relation_to_head,
                "voter_id": m.voter_id,
                "is_eligible_to_vote": m.is_eligible_to_vote,
                "is_voter_verified": m.is_voter_verified,
            }
            for m in family_members
        ],
        "linked_voters": [
            {
                "voter_id": v.voter_id,
                "epic_no": v.epic_no,
                "voter_name": v.voter_name,
                "age": v.age,
                "gender": v.gender,
                "survey_date": v.survey_date.isoformat() if v.survey_date else None,
            }
            for v in linked_voters
        ]
    }


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
    """Get all forms submitted by a specific volunteer"""
    query = db.query(FormData).filter(FormData.volunteer_id == volunteer_id)

    if from_date and to_date:
        query = query.filter(
            and_(
                func.date(FormData.visit_date) >= from_date,
                func.date(FormData.visit_date) <= to_date
            )
        )

    forms = query.order_by(FormData.created_at.desc()).all()

    return [
        {
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
            'family_members': form.family_members,
            'family_members_count': form.family_members_count,
            'voter_id': form.voter_id,
            'aadhar': form.aadhar,
            'voter_names': form.voter_names,
            'voter_ages': form.voter_ages,
            'voter_relation': form.voter_relation,
            'knows_corporator': form.knows_corporator,
            'corporator_name': form.corporator_name,
            'knows_politician': form.knows_politician,
            'other_politicians_known': form.other_politicians_known,
            'current_party_support': form.current_party_support,
            'favourite_party': form.favourite_party,
            'services_received': form.services_received,
            'service_frequency': form.service_frequency,
            'politician_visit_freq': form.politician_visit_freq,
            'satisfaction_with_corporator': form.satisfaction_with_corporator,
            'satisfaction_with_service': form.satisfaction_with_service,
            'attended_events': form.attended_events,
            'work_done_in_ward': form.work_done_in_ward,
            'work_details': form.work_details,
            'income_range': form.income_range,
            'main_occupation': form.main_occupation,
            'education': form.education,
            'highest_education': form.highest_education,
            'housing_type': form.housing_type,
            'govt_schemes': form.govt_schemes,
            'children_count': form.children_count,
            'is_voted': form.is_voted,
            'voting_status': form.voting_status,
            'visit_date': str(form.visit_date) if form.visit_date else None,
            'volunteer_name': form.volunteer_name,
            'remarks': form.remarks,
            'corporator_division': form.corporator_division,
            'zone': form.zone,
            'image_url': form.image_url,
            'person_image_url': form.person_image_url,
            'latitude': float(form.latitude) if form.latitude else None,
            'longitude': float(form.longitude) if form.longitude else None,
            'location_accuracy': float(form.location_accuracy) if form.location_accuracy else None,
            'created_at': form.created_at.isoformat() if form.created_at else None,
            'updated_at': form.updated_at.isoformat() if form.updated_at else None,
        }
        for form in forms
    ]


@router.get("/AllformData")
def get_all_forms(
    from_date: Optional[date] = Query(None, alias="fromDate"),
    to_date: Optional[date] = Query(None, alias="toDate"),
    politician_id: int = Depends(get_politician_id_from_token),
    db: Session = Depends(get_db)
):
    """Get all forms — accessible by both politician and volunteer"""
    volunteer_ids = [v[0] for v in db.query(Volunteer.id).filter(
        Volunteer.politician_id == politician_id
    ).all()]

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

    return {"data": [
        {
            'id': form.id,
            'household_name': form.household_name,
            'area': form.area,
            'caste': form.caste,
            'current_party_support': form.current_party_support,
            'visit_date': str(form.visit_date) if form.visit_date else None,
            'created_at': form.created_at.isoformat() if form.created_at else None,
        }
        for form in forms
    ]}


@router.get("/map-pins")
def get_map_pins(
    politician_id: int = Depends(get_politician_id_from_token),
    db: Session = Depends(get_db)
):
    """Get all GPS-tagged form submissions for map visualization"""
    volunteer_ids = db.query(Volunteer.id).filter(
        Volunteer.politician_id == politician_id
    ).subquery()

    pins = db.query(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.latitude.isnot(None),
        FormData.longitude.isnot(None)
    ).order_by(FormData.visit_date.desc()).all()

    return pins


# ========================================
# DASHBOARD HELPERS
# ========================================

def get_politician_volunteer_ids(politician_id: int, db: Session) -> List[int]:
    return [v[0] for v in db.query(Volunteer.id).filter(
        Volunteer.politician_id == politician_id
    ).all()]


# ========================================
# 1. OVERVIEW
# ========================================

@router.get("/dashboard/overview")
def get_dashboard_overview(
    politician_id: int = Depends(get_politician_id_from_token),
    db: Session = Depends(get_db)
):
    """Comprehensive overview stats"""
    volunteer_ids = get_politician_volunteer_ids(politician_id, db)

    if not volunteer_ids:
        return {
            "total_households": 0, "total_family_members": 0,
            "total_eligible_voters": 0, "total_voters_surveyed": 0,
            "total_volunteers": 0, "active_volunteers": 0,
            "surveys_today": 0, "surveys_this_week": 0,
            "surveys_this_month": 0, "avg_family_size": 0,
            "data_completeness": 0, "survey_coverage": 0
        }

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

    total_voters_surveyed = db.query(func.count(Voter.voter_id)).filter(
        Voter.is_surveyed == True
    ).scalar() or 0

    total_volunteers = db.query(func.count(Volunteer.id)).filter(
        Volunteer.politician_id == politician_id
    ).scalar() or 0

    active_volunteers = db.query(func.count(Volunteer.id)).filter(
        Volunteer.politician_id == politician_id,
        Volunteer.is_active == True
    ).scalar() or 0

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

    avg_family_size = db.query(func.avg(FormData.family_members_count)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.family_members_count.isnot(None)
    ).scalar() or 0

    surveys_with_gps = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.latitude.isnot(None),
        FormData.longitude.isnot(None)
    ).scalar() or 0

    data_completeness = (surveys_with_gps / total_households * 100) if total_households > 0 else 0
    total_voters = db.query(func.count(Voter.voter_id)).scalar() or 1
    survey_coverage = (total_voters_surveyed / total_voters * 100) if total_voters > 0 else 0

    return {
        "total_households": total_households,
        "total_family_members": total_family_members,
        "total_eligible_voters": total_eligible_voters,
        "total_voters_surveyed": total_voters_surveyed,
        "total_volunteers": total_volunteers,
        "active_volunteers": active_volunteers,
        "surveys_today": surveys_today,
        "surveys_this_week": surveys_this_week,
        "surveys_this_month": surveys_this_month,
        "avg_family_size": round(float(avg_family_size), 2),
        "data_completeness": round(data_completeness, 2),
        "survey_coverage": round(survey_coverage, 2)
    }


# ========================================
# 2. DEMOGRAPHICS
# ========================================

@router.get("/dashboard/demographics")
def get_demographics(
    politician_id: int = Depends(get_politician_id_from_token),
    db: Session = Depends(get_db)
):
    """Demographic breakdown"""
    volunteer_ids = get_politician_volunteer_ids(politician_id, db)

    if not volunteer_ids:
        return {
            "age_distribution": {}, "gender_distribution": {},
            "caste_distribution": {}, "religion_distribution": {},
            "education_distribution": {}, "income_distribution": {},
            "occupation_distribution": {}, "housing_distribution": {}
        }

    members = db.query(FamilyMember.age).join(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FamilyMember.age.isnot(None)
    ).all()

    age_distribution = {
        'Children (0-17)': 0, 'Young Adults (18-25)': 0,
        'Adults (26-40)': 0, 'Middle Age (41-60)': 0, 'Senior Citizens (60+)': 0
    }
    for (age,) in members:
        if age < 18: age_distribution['Children (0-17)'] += 1
        elif age <= 25: age_distribution['Young Adults (18-25)'] += 1
        elif age <= 40: age_distribution['Adults (26-40)'] += 1
        elif age <= 60: age_distribution['Middle Age (41-60)'] += 1
        else: age_distribution['Senior Citizens (60+)'] += 1

    def group_by(column, filter_none=True):
        data = db.query(column, func.count()).filter(
            FormData.volunteer_id.in_(volunteer_ids),
            column.isnot(None) if filter_none else True
        ).group_by(column).all()
        return {k: v for k, v in data if k}

    gender_data = db.query(FamilyMember.gender, func.count(FamilyMember.member_id)).join(FormData).filter(
        FormData.volunteer_id.in_(volunteer_ids), FamilyMember.gender.isnot(None)
    ).group_by(FamilyMember.gender).all()

    return {
        "age_distribution": age_distribution,
        "gender_distribution": {g: c for g, c in gender_data if g},
        "caste_distribution": group_by(FormData.caste),
        "religion_distribution": group_by(FormData.religion),
        "education_distribution": group_by(FormData.highest_education),
        "income_distribution": group_by(FormData.income_range),
        "occupation_distribution": group_by(FormData.main_occupation),
        "housing_distribution": group_by(FormData.housing_type),
    }


# ========================================
# 3. POLITICAL INSIGHTS
# ========================================

@router.get("/dashboard/political-insights")
def get_political_insights(
    politician_id: int = Depends(get_politician_id_from_token),
    db: Session = Depends(get_db)
):
    """Political analytics"""
    volunteer_ids = get_politician_volunteer_ids(politician_id, db)

    if not volunteer_ids:
        return {
            "party_support": {}, "favourite_party": {},
            "corporator_recognition": {}, "political_engagement": {},
            "win_probability": {}
        }

    party_support_data = db.query(FormData.current_party_support, func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.current_party_support.isnot(None),
        FormData.current_party_support != ''
    ).group_by(FormData.current_party_support).all()

    favourite_party_data = db.query(FormData.favourite_party, func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.favourite_party.isnot(None),
        FormData.favourite_party != ''
    ).group_by(FormData.favourite_party).all()

    total_surveys = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).scalar() or 1

    knows_corporator = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.knows_corporator == True
    ).scalar() or 0

    attended_events = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.attended_events == True
    ).scalar() or 0

    aware_of_work = db.query(func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.work_done_in_ward == True
    ).scalar() or 0

    your_party = "YourPartyName"  # TODO: pull from config/settings

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

    return {
        "party_support": {p: c for p, c in party_support_data if p},
        "favourite_party": {p: c for p, c in favourite_party_data if p},
        "corporator_recognition": {
            "knows_corporator": knows_corporator,
            "does_not_know": total_surveys - knows_corporator,
            "recognition_rate": round((knows_corporator / total_surveys * 100), 2)
        },
        "political_engagement": {
            "attended_events": attended_events,
            "not_attended": total_surveys - attended_events,
            "aware_of_work_done": aware_of_work,
            "engagement_rate": round((attended_events / total_surveys * 100), 2)
        },
        "win_probability": {
            "strong_supporters": strong_supporters,
            "potential_supporters": potential_supporters,
            "swing_voters": swing_voters,
            "total_reachable": strong_supporters + potential_supporters + swing_voters
        }
    }


# ========================================
# 4. GEOGRAPHIC ANALYTICS
# ========================================

@router.get("/dashboard/geographic")
def get_geographic_analytics(
    politician_id: int = Depends(get_politician_id_from_token),
    db: Session = Depends(get_db)
):
    """Area/zone-wise distribution"""
    volunteer_ids = get_politician_volunteer_ids(politician_id, db)

    if not volunteer_ids:
        return {"by_area": {}, "by_zone": {}, "by_colony": {}, "coverage_map": []}

    area_data = db.query(
        FormData.area,
        func.count(FormData.id).label('households'),
        func.count(FamilyMember.member_id).label('voters')
    ).outerjoin(FamilyMember).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.area.isnot(None)
    ).group_by(FormData.area).all()

    zone_data = db.query(FormData.zone, func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids), FormData.zone.isnot(None)
    ).group_by(FormData.zone).all()

    colony_data = db.query(FormData.colony, func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids), FormData.colony.isnot(None)
    ).group_by(FormData.colony).all()

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

    return {
        "by_area": {
            area: {"households": h, "voters": v or 0}
            for area, h, v in area_data if area
        },
        "by_zone": {z: n for z, n in zone_data if z},
        "by_colony": {c: n for c, n in colony_data if c},
        "coverage_map": [
            {"area": area, "latitude": float(lat), "longitude": float(lng), "survey_count": count}
            for area, lat, lng, count in coverage_data if area
        ]
    }


# ========================================
# 5. SERVICE ANALYTICS
# ========================================

@router.get("/dashboard/services")
def get_service_analytics(
    politician_id: int = Depends(get_politician_id_from_token),
    db: Session = Depends(get_db)
):
    """Service distribution and satisfaction"""
    volunteer_ids = get_politician_volunteer_ids(politician_id, db)

    if not volunteer_ids:
        return {"services_provided": {}, "satisfaction_levels": {},
                "service_frequency": {}, "govt_schemes": {}}

    def count_csv_field(column):
        rows = db.query(column).filter(
            FormData.volunteer_id.in_(volunteer_ids), column.isnot(None)
        ).all()
        counts = {}
        for (val,) in rows:
            if val:
                for item in [x.strip() for x in val.split(',')]:
                    if item:
                        counts[item] = counts.get(item, 0) + 1
        return counts

    satisfaction_data = db.query(FormData.satisfaction_with_service, func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.satisfaction_with_service.isnot(None)
    ).group_by(FormData.satisfaction_with_service).all()

    frequency_data = db.query(FormData.service_frequency, func.count(FormData.id)).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.service_frequency.isnot(None)
    ).group_by(FormData.service_frequency).all()

    return {
        "services_provided": count_csv_field(FormData.services_received),
        "satisfaction_levels": {s: c for s, c in satisfaction_data if s},
        "service_frequency": {f: c for f, c in frequency_data if f},
        "govt_schemes": count_csv_field(FormData.govt_schemes),
    }


# ========================================
# 6. VOLUNTEER PERFORMANCE
# ========================================

@router.get("/dashboard/volunteer-performance")
def get_volunteer_performance(
    politician_id: int = Depends(get_politician_id_from_token),
    db: Session = Depends(get_db)
):
    """Volunteer performance metrics"""
    volunteers = db.query(Volunteer).filter(
        Volunteer.politician_id == politician_id
    ).all()

    stats = []
    for v in volunteers:
        forms_count = db.query(func.count(FormData.id)).filter(
            FormData.volunteer_id == v.id
        ).scalar() or 0

        voters_count = db.query(func.count(FamilyMember.member_id)).join(FormData).filter(
            FormData.volunteer_id == v.id,
            FamilyMember.is_eligible_to_vote == True
        ).scalar() or 0

        last_submission = db.query(func.max(FormData.created_at)).filter(
            FormData.volunteer_id == v.id
        ).scalar()

        surveys_with_gps = db.query(func.count(FormData.id)).filter(
            FormData.volunteer_id == v.id,
            FormData.latitude.isnot(None)
        ).scalar() or 0

        areas_covered = db.query(func.count(distinct(FormData.area))).filter(
            FormData.volunteer_id == v.id,
            FormData.area.isnot(None)
        ).scalar() or 0

        data_quality = (surveys_with_gps / forms_count * 100) if forms_count > 0 else 0

        stats.append({
            "id": v.id,
            "username": v.username,
            "email": v.email,
            "mobile_number": v.phone_number,  # ✅ fixed: was v.mobile_number
            "is_active": v.is_active,
            "total_surveys": forms_count,
            "total_voters": voters_count,
            "data_quality_score": round(data_quality, 2),
            "areas_covered": areas_covered,
            "last_submission": last_submission.isoformat() if last_submission else None
        })

    stats.sort(key=lambda x: x['total_surveys'], reverse=True)

    return {
        "total_volunteers": len(volunteers),
        "active_volunteers": sum(1 for v in volunteers if v.is_active),
        "volunteers": stats
    }


# ========================================
# 7. TIME TRENDS
# ========================================

@router.get("/dashboard/trends")
def get_time_trends(
    days: int = Query(30, ge=7, le=90),
    politician_id: int = Depends(get_politician_id_from_token),
    db: Session = Depends(get_db)
):
    """Survey trends over time"""
    volunteer_ids = get_politician_volunteer_ids(politician_id, db)

    if not volunteer_ids:
        return {"daily_surveys": [], "period_days": days}

    start_date = datetime.now().date() - timedelta(days=days)

    daily_data = db.query(
        func.date(FormData.created_at).label('date'),
        func.count(FormData.id).label('count')
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        func.date(FormData.created_at) >= start_date
    ).group_by(func.date(FormData.created_at)).order_by('date').all()

    return {
        "daily_surveys": [{"date": str(d), "count": c} for d, c in daily_data],
        "period_days": days
    }


# ========================================
# INDIVIDUAL VOLUNTEER DASHBOARDS
# ========================================

@router.get("/volunteer/dashboard/summary/{volunteer_id}")
def get_volunteer_dashboard_summary(
    volunteer_id: int,
    db: Session = Depends(get_db)
):
    """Dashboard summary for a specific volunteer"""
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

    return {
        "total_households": total_households,
        "total_voters": total_voters,
        "total_supporters": total_supporters,
        "satisfaction_count": {
            "VerySatisfied": sum(1 for f in feedback if f[0] == 'Yes'),
            "Satisfied": sum(1 for f in feedback if f[0] == 'Moderate'),
            "Neutral": 0,
            "Dissatisfied": sum(1 for f in feedback if f[0] == 'No')
        }
    }


@router.get("/volunteer/dashboard/voter-demographics/{volunteer_id}")
def get_volunteer_voter_demographics(
    volunteer_id: int,
    db: Session = Depends(get_db)
):
    """Age and gender distribution for a specific volunteer"""
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
        gender_distribution[gender if gender in gender_distribution else 'Other'] += 1

    return {"age_groups": age_groups, "gender_distribution": gender_distribution}


@router.get("/volunteer/dashboard/political-support/{volunteer_id}")
def get_volunteer_political_support(
    volunteer_id: int,
    db: Session = Depends(get_db)
):
    """Political support breakdown for a specific volunteer"""
    data = db.query(FormData.current_party_support, func.count(FormData.id)).filter(
        FormData.volunteer_id == volunteer_id,
        FormData.current_party_support.isnot(None),
        FormData.current_party_support != ''
    ).group_by(FormData.current_party_support).all()

    return {party: count for party, count in data if party}


@router.get("/volunteer/dashboard/service-feedback/{volunteer_id}")
def get_volunteer_service_feedback(
    volunteer_id: int,
    db: Session = Depends(get_db)
):
    """Service feedback for a specific volunteer"""
    services_data = db.query(FormData.services_received).filter(
        FormData.volunteer_id == volunteer_id,
        FormData.services_received.isnot(None)
    ).all()

    services_count = {}
    for (val,) in services_data:
        if val:
            for s in [x.strip() for x in val.split(',')]:
                if s:
                    services_count[s] = services_count.get(s, 0) + 1

    satisfaction_data = db.query(FormData.satisfaction_with_service, func.count(FormData.id)).filter(
        FormData.volunteer_id == volunteer_id,
        FormData.satisfaction_with_service.isnot(None)
    ).group_by(FormData.satisfaction_with_service).all()

    return {
        "services_provided": services_count,
        "satisfaction_levels": {s: c for s, c in satisfaction_data if s}
    }


@router.get("/volunteer/dashboard/volunteer-overview/{volunteer_id}")
def get_volunteer_overview_individual(
    volunteer_id: int,
    db: Session = Depends(get_db)
):
    """Full overview for a specific volunteer"""
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

    return {
        "volunteer": {
            "id": volunteer.id,
            "username": volunteer.username,
            "email": volunteer.email,
            "mobile_number": volunteer.phone_number,  # ✅ fixed: was volunteer.mobile_number
            "is_active": volunteer.is_active
        },
        "total_forms": forms_count,
        "total_voters": voters_count,
        "last_submission": last_submission.isoformat() if last_submission else None,
        "recent_submissions": [
            {
                "id": f.id,
                "household_name": f.household_name,
                "address": f.address,
                "visit_date": str(f.visit_date) if f.visit_date else None,
                "created_at": f.created_at.isoformat() if f.created_at else None
            }
            for f in recent_forms
        ]
    }



# ============================================================
# HOME SCREEN SUMMARY — Single combined call for HomeScreen
# ============================================================

@router.get("/dashboard/home-summary")
def get_home_summary(
    politician_id: int = Depends(get_politician_id_from_token),
    db: Session = Depends(get_db)
):
    """
    Single optimized endpoint for HomeScreen stats.
    Combines overview + scoped voter count in one DB round-trip.
    """

    # ── Step 1: get all volunteer IDs under this politician ──
    volunteer_ids = get_politician_volunteer_ids(politician_id, db)

    # ── Step 2: get areas assigned to this politician ────────
    user_area_ids = [
        a[0] for a in db.query(UserArea.area_id)
        .filter(UserArea.user_id == politician_id)
        .all()
    ]

    # ── Step 3: get part IDs inside those areas ──────────────
    part_ids = []
    if user_area_ids:
        part_ids = [
            p[0] for p in db.query(Part.part_id)
            .filter(Part.area_id.in_(user_area_ids))
            .all()
        ]

    # ── Step 4: date helpers (needed even in early return) ───
    today     = datetime.now().date()
    week_ago  = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # ── Step 5: total voters scoped to politician's areas ────
    total_voters = 0
    if part_ids:
        total_voters = db.query(
            func.count(Voter.voter_id)
        ).filter(
            Voter.part_id.in_(part_ids)
        ).scalar() or 0

    # ── Step 6: early return if no volunteers yet ────────────
    if not volunteer_ids:
        return {
            "total_voters":            total_voters,
            "total_voters_surveyed":   0,
            "voters_surveyed_today":   0,       # ✅ new
            "survey_coverage":         0.0,
            "total_volunteers":        0,
            "active_volunteers":       0,
            "total_households":        0,
            "surveys_today":           0,
            "surveys_this_week":       0,
            "surveys_this_month":      0,
            "total_family_members":    0,
            "total_eligible_voters":   0,
            "avg_family_size":         0.0,
            "data_completeness":       0.0,
        }

    # ── Step 7: all the stats ─────────────────────────────────

    total_households = db.query(
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids)
    ).scalar() or 0

    total_family_members = (
        db.query(func.count(FamilyMember.member_id))
        .join(FormData)
        .filter(FormData.volunteer_id.in_(volunteer_ids))
        .scalar() or 0
    )

    total_eligible_voters = (
        db.query(func.count(FamilyMember.member_id))
        .join(FormData)
        .filter(
            FormData.volunteer_id.in_(volunteer_ids),
            FamilyMember.is_eligible_to_vote == True,
        )
        .scalar() or 0
    )

    # ── Scoped surveyed voters (cumulative) ──────────────────
    total_voters_surveyed = 0
    if part_ids:
        total_voters_surveyed = db.query(
            func.count(Voter.voter_id)
        ).filter(
            Voter.part_id.in_(part_ids),
            Voter.is_surveyed == True,
        ).scalar() or 0

    # ── Voters surveyed TODAY using survey_date ───────────────
    voters_surveyed_today = 0
    if part_ids:
        voters_surveyed_today = db.query(
            func.count(Voter.voter_id)
        ).filter(
            Voter.part_id.in_(part_ids),
            Voter.is_surveyed == True,
            func.date(Voter.survey_date) == today,   # ← survey_date column
        ).scalar() or 0

    total_volunteers = db.query(
        func.count(Volunteer.id)
    ).filter(
        Volunteer.politician_id == politician_id
    ).scalar() or 0

    active_volunteers = db.query(
        func.count(Volunteer.id)
    ).filter(
        Volunteer.politician_id == politician_id,
        Volunteer.is_active == True,
    ).scalar() or 0

    surveys_today = db.query(
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        func.date(FormData.created_at) == today,
    ).scalar() or 0

    surveys_this_week = db.query(
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        func.date(FormData.created_at) >= week_ago,
    ).scalar() or 0

    surveys_this_month = db.query(
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        func.date(FormData.created_at) >= month_ago,
    ).scalar() or 0

    avg_family_size = (
        db.query(func.avg(FormData.family_members_count))
        .filter(
            FormData.volunteer_id.in_(volunteer_ids),
            FormData.family_members_count.isnot(None),
        )
        .scalar() or 0
    )

    surveys_with_gps = db.query(
        func.count(FormData.id)
    ).filter(
        FormData.volunteer_id.in_(volunteer_ids),
        FormData.latitude.isnot(None),
        FormData.longitude.isnot(None),
    ).scalar() or 0

    data_completeness = (
        surveys_with_gps / total_households * 100
        if total_households > 0 else 0
    )

    survey_coverage = (
        total_voters_surveyed / total_voters * 100
        if total_voters > 0 else 0
    )

    return {
        # ── Voter scope (area-scoped) ──
        "total_voters":            total_voters,
        "total_voters_surveyed":   total_voters_surveyed,
        "voters_surveyed_today":   voters_surveyed_today,   # ✅ new
        "survey_coverage":         round(survey_coverage, 2),

        # ── Volunteer scope ──
        "total_volunteers":        total_volunteers,
        "active_volunteers":       active_volunteers,

        # ── Door visit / form scope ──
        "total_households":        total_households,
        "surveys_today":           surveys_today,
        "surveys_this_week":       surveys_this_week,
        "surveys_this_month":      surveys_this_month,

        # ── Extra context ──
        "total_family_members":    total_family_members,
        "total_eligible_voters":   total_eligible_voters,
        "avg_family_size":         round(float(avg_family_size), 2),
        "data_completeness":       round(data_completeness, 2),
    }
