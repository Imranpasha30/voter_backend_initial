from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import func  # ✅ Add this
from typing import List, Optional

from app.db.session import get_db
from app.models.user import User
from app.models.polling_voter import PollingVoter  # ✅ Keep at top
from app.api.deps import get_current_user
from app.services.polling_voter_service import PollingVoterService
from app.schemas.polling_voter import (
    PollingVoterResponse,
    PollingVoterUpdate,
    PollingVoterListResponse,
    MunicipalityResponse,
    PollingStationResponse,
    CSVUploadResponse
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload-csv", response_model=CSVUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload CSV file and import polling voter data"""
    logger.info(f"📤 CSV Upload by user: {current_user.full_name}")
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are allowed"
        )
    
    try:
        content = await file.read()
        csv_content = content.decode('utf-8')
        result = PollingVoterService.import_from_csv(db, csv_content)
        return result
    except Exception as e:
        logger.exception("❌ CSV upload failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process CSV: {str(e)}"
        )


@router.get("/municipalities", response_model=List[MunicipalityResponse])
def get_municipalities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of all municipalities with voter counts"""
    municipalities = PollingVoterService.get_municipalities(db)
    return municipalities


@router.get("/polling-stations", response_model=List[PollingStationResponse])
def get_polling_stations(
    municipality: str = Query(..., description="Municipality name"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get polling stations for a specific municipality"""
    stations = PollingVoterService.get_polling_stations(db, municipality)
    return stations


@router.get("/voters")
def get_voters(
    municipality: str = Query(..., description="Municipality name"),
    polling_station_no: str = Query(..., description="Polling station number"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voters for a specific polling station with pagination"""
    skip = (page - 1) * page_size
    result = PollingVoterService.get_voters_by_polling_station(
        db, municipality, polling_station_no, skip, page_size
    )
    
    voters_data = [
        {
            "id": voter.id,
            "voter_id": voter.voter_id,
            "ward_no": voter.ward_no,
            "district": voter.district,
            "municipality": voter.municipality,
            "polling_station_no": voter.polling_station_no,
            "polling_station_location": voter.polling_station_location,
            "serial_no": voter.serial_no,
            "voter_name": voter.voter_name,
            "relation_name": voter.relation_name,
            "age": voter.age,
            "gender": voter.gender,
            "house_no": voter.house_no,
            "date_time": voter.date_time,
            "pdf_url": voter.pdf_url,
            "created_at": voter.created_at.isoformat() if voter.created_at else None,
            "updated_at": voter.updated_at.isoformat() if voter.updated_at else None,
        }
        for voter in result["voters"]
    ]
    
    return {
        "success": True,
        "voters": voters_data,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"]
    }


@router.get("/voter/{voter_id}", response_model=PollingVoterResponse)
def get_voter_details(
    voter_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed information for a specific voter with PDF URL"""
    voter = PollingVoterService.get_voter_by_id(db, voter_id)
    
    if not voter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voter with ID {voter_id} not found"
        )
    
    return voter


@router.get("/search")
def search_voters(
    query: str = Query(..., min_length=1, description="Search query"),
    municipality: Optional[str] = Query(None, description="Filter by municipality"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search voters by name or voter ID"""
    skip = (page - 1) * page_size
    result = PollingVoterService.search_voters(
        db, query, municipality, skip, page_size
    )
    
    voters_data = [
        {
            "id": voter.id,
            "voter_id": voter.voter_id,
            "ward_no": voter.ward_no,
            "district": voter.district,
            "municipality": voter.municipality,
            "polling_station_no": voter.polling_station_no,
            "polling_station_location": voter.polling_station_location,
            "serial_no": voter.serial_no,
            "voter_name": voter.voter_name,
            "relation_name": voter.relation_name,
            "age": voter.age,
            "gender": voter.gender,
            "house_no": voter.house_no,
            "date_time": voter.date_time,
            "pdf_url": voter.pdf_url,
            "created_at": voter.created_at.isoformat() if voter.created_at else None,
            "updated_at": voter.updated_at.isoformat() if voter.updated_at else None,
        }
        for voter in result["voters"]
    ]
    
    return {
        "success": True,
        "voters": voters_data,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"]
    }


# ✅ ONLY ONE /stats ENDPOINT
@router.get("/stats")
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive voter statistics"""
    total_voters = db.query(func.count(PollingVoter.id)).scalar() or 0
    total_municipalities = db.query(func.count(func.distinct(PollingVoter.municipality))).scalar() or 0
    total_stations = db.query(func.count(func.distinct(PollingVoter.polling_station_no))).scalar() or 0
    
    # Gender stats
    male_count = db.query(func.count(PollingVoter.id)).filter(
        func.lower(PollingVoter.gender) == 'male'
    ).scalar() or 0
    
    female_count = db.query(func.count(PollingVoter.id)).filter(
        func.lower(PollingVoter.gender) == 'female'
    ).scalar() or 0
    
    other_count = total_voters - (male_count + female_count)
    
    # Age stats
    age_18_25 = db.query(func.count(PollingVoter.id)).filter(
        PollingVoter.age.between(18, 25)
    ).scalar() or 0
    
    age_26_35 = db.query(func.count(PollingVoter.id)).filter(
        PollingVoter.age.between(26, 35)
    ).scalar() or 0
    
    age_36_50 = db.query(func.count(PollingVoter.id)).filter(
        PollingVoter.age.between(36, 50)
    ).scalar() or 0
    
    age_51_65 = db.query(func.count(PollingVoter.id)).filter(
        PollingVoter.age.between(51, 65)
    ).scalar() or 0
    
    age_65_plus = db.query(func.count(PollingVoter.id)).filter(
        PollingVoter.age >= 66
    ).scalar() or 0
    
    return {
        "success": True,
        "total_voters": total_voters,
        "total_municipalities": total_municipalities,
        "total_polling_stations": total_stations,
        "male_count": male_count,
        "female_count": female_count,
        "other_count": other_count,
        "age_18_25": age_18_25,
        "age_26_35": age_26_35,
        "age_36_50": age_36_50,
        "age_51_65": age_51_65,
        "age_65_plus": age_65_plus,
    }


@router.get("/filter")
def filter_voters(
    filter_type: str = Query(..., description="Filter type: 'gender' or 'age'"),
    filter_value: str = Query(..., description="Filter value: 'male', 'female', '18-25', etc."),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Filter voters by gender or age range"""
    skip = (page - 1) * page_size
    
    query = db.query(PollingVoter)
    
    if filter_type == 'gender':
        query = query.filter(func.lower(PollingVoter.gender) == filter_value.lower())
    elif filter_type == 'age':
        if filter_value == '18-25':
            query = query.filter(PollingVoter.age.between(18, 25))
        elif filter_value == '26-35' or filter_value == '18-35':
            query = query.filter(PollingVoter.age.between(18 if filter_value == '18-35' else 26, 35))
        elif filter_value == '36-50':
            query = query.filter(PollingVoter.age.between(36, 50))
        elif filter_value == '51-65':
            query = query.filter(PollingVoter.age.between(51, 65))
        elif filter_value == '65+':
            query = query.filter(PollingVoter.age >= 66)
    
    total = query.count()
    voters = query.offset(skip).limit(page_size).all()
    
    voters_data = [
        {
            "id": voter.id,
            "voter_id": voter.voter_id,
            "ward_no": voter.ward_no,
            "district": voter.district,
            "municipality": voter.municipality,
            "polling_station_no": voter.polling_station_no,
            "polling_station_location": voter.polling_station_location,
            "serial_no": voter.serial_no,
            "voter_name": voter.voter_name,
            "relation_name": voter.relation_name,
            "age": voter.age,
            "gender": voter.gender,
            "house_no": voter.house_no,
            "date_time": voter.date_time,
            "pdf_url": voter.pdf_url,
            "created_at": voter.created_at.isoformat() if voter.created_at else None,
            "updated_at": voter.updated_at.isoformat() if voter.updated_at else None,
        }
        for voter in voters
    ]
    
    return {
        "success": True,
        "voters": voters_data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }




# ✅ NEW: PATCH endpoint to update voter
@router.patch("/voter/{voter_id}", response_model=PollingVoterResponse)
def update_voter(
    voter_id: str,
    update_data: PollingVoterUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update voter tracking information (phone, voting status, is_voted)"""
    logger.info(f"📝 Updating voter {voter_id} by {current_user.full_name}")
    
    try:
        updated_voter = PollingVoterService.update_voter(
            db=db,
            voter_id=voter_id,
            phone_number=update_data.phone_number,
            is_voted=update_data.is_voted,
            voting_status=update_data.voting_status
        )
        
        if not updated_voter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Voter with ID {voter_id} not found"
            )
        
        return updated_voter
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"❌ Update failed for voter {voter_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update voter: {str(e)}"
        )


# ✅ NEW: Bulk update endpoint
@router.post("/bulk-update")
def bulk_update_voters(
    voter_ids: List[str],
    voting_status: Optional[str] = None,
    is_voted: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Bulk update multiple voters"""
    logger.info(f"📦 Bulk updating {len(voter_ids)} voters by {current_user.full_name}")
    
    try:
        result = PollingVoterService.bulk_update_voters(
            db=db,
            voter_ids=voter_ids,
            voting_status=voting_status,
            is_voted=is_voted
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("❌ Bulk update failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk update failed: {str(e)}"
        )


# Update existing get_voters endpoint to include new fields
@router.get("/voters")
def get_voters(
    municipality: str = Query(..., description="Municipality name"),
    polling_station_no: str = Query(..., description="Polling station number"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voters for a specific polling station with pagination"""
    skip = (page - 1) * page_size
    result = PollingVoterService.get_voters_by_polling_station(
        db, municipality, polling_station_no, skip, page_size
    )
    
    voters_data = [
        {
            "id": voter.id,
            "voter_id": voter.voter_id,
            "ward_no": voter.ward_no,
            "district": voter.district,
            "municipality": voter.municipality,
            "polling_station_no": voter.polling_station_no,
            "polling_station_location": voter.polling_station_location,
            "serial_no": voter.serial_no,
            "voter_name": voter.voter_name,
            "relation_name": voter.relation_name,
            "age": voter.age,
            "gender": voter.gender,
            "house_no": voter.house_no,
            "date_time": voter.date_time,
            "pdf_url": voter.pdf_url,
            "phone_number": voter.phone_number,  # ✅ NEW
            "is_voted": voter.is_voted,  # ✅ NEW
            "voting_status": voter.voting_status,  # ✅ NEW
            "created_at": voter.created_at.isoformat() if voter.created_at else None,
            "updated_at": voter.updated_at.isoformat() if voter.updated_at else None,
        }
        for voter in result["voters"]
    ]
    
    return {
        "success": True,
        "voters": voters_data,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"]
    }


# Update get_voter_details to include new fields
@router.get("/voter/{voter_id}", response_model=PollingVoterResponse)
def get_voter_details(
    voter_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed information for a specific voter"""
    voter = PollingVoterService.get_voter_by_id(db, voter_id)
    
    if not voter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voter with ID {voter_id} not found"
        )
    
    return voter


# Update search endpoint to include new fields
@router.get("/search")
def search_voters(
    query: str = Query(..., min_length=1, description="Search query"),
    municipality: Optional[str] = Query(None, description="Filter by municipality"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search voters by name or voter ID"""
    skip = (page - 1) * page_size
    result = PollingVoterService.search_voters(
        db, query, municipality, skip, page_size
    )
    
    voters_data = [
        {
            "id": voter.id,
            "voter_id": voter.voter_id,
            "ward_no": voter.ward_no,
            "district": voter.district,
            "municipality": voter.municipality,
            "polling_station_no": voter.polling_station_no,
            "polling_station_location": voter.polling_station_location,
            "serial_no": voter.serial_no,
            "voter_name": voter.voter_name,
            "relation_name": voter.relation_name,
            "age": voter.age,
            "gender": voter.gender,
            "house_no": voter.house_no,
            "date_time": voter.date_time,
            "pdf_url": voter.pdf_url,
            "phone_number": voter.phone_number,  # ✅ NEW
            "is_voted": voter.is_voted,  # ✅ NEW
            "voting_status": voter.voting_status,  # ✅ NEW
            "created_at": voter.created_at.isoformat() if voter.created_at else None,
            "updated_at": voter.updated_at.isoformat() if voter.updated_at else None,
        }
        for voter in result["voters"]
    ]
    
    return {
        "success": True,
        "voters": voters_data,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"]
    }


# Update filter endpoint to include new fields
@router.get("/filter")
def filter_voters(
    filter_type: str = Query(..., description="Filter type: 'gender' or 'age'"),
    filter_value: str = Query(..., description="Filter value: 'male', 'female', '18-25', etc."),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Filter voters by gender or age range"""
    skip = (page - 1) * page_size
    
    query = db.query(PollingVoter)
    
    if filter_type == 'gender':
        query = query.filter(func.lower(PollingVoter.gender) == filter_value.lower())
    elif filter_type == 'age':
        if filter_value == '18-25':
            query = query.filter(PollingVoter.age.between(18, 25))
        elif filter_value == '26-35' or filter_value == '18-35':
            query = query.filter(PollingVoter.age.between(18 if filter_value == '18-35' else 26, 35))
        elif filter_value == '36-50':
            query = query.filter(PollingVoter.age.between(36, 50))
        elif filter_value == '51-65':
            query = query.filter(PollingVoter.age.between(51, 65))
        elif filter_value == '65+':
            query = query.filter(PollingVoter.age >= 66)
    
    total = query.count()
    voters = query.offset(skip).limit(page_size).all()
    
    voters_data = [
        {
            "id": voter.id,
            "voter_id": voter.voter_id,
            "ward_no": voter.ward_no,
            "district": voter.district,
            "municipality": voter.municipality,
            "polling_station_no": voter.polling_station_no,
            "polling_station_location": voter.polling_station_location,
            "serial_no": voter.serial_no,
            "voter_name": voter.voter_name,
            "relation_name": voter.relation_name,
            "age": voter.age,
            "gender": voter.gender,
            "house_no": voter.house_no,
            "date_time": voter.date_time,
            "pdf_url": voter.pdf_url,
            "phone_number": voter.phone_number,  # ✅ NEW
            "is_voted": voter.is_voted,  # ✅ NEW
            "voting_status": voter.voting_status,  # ✅ NEW
            "created_at": voter.created_at.isoformat() if voter.created_at else None,
            "updated_at": voter.updated_at.isoformat() if voter.updated_at else None,
        }
        for voter in voters
    ]
    
    return {
        "success": True,
        "voters": voters_data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


# Keep existing stats and other endpoints...
@router.get("/stats")
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive voter statistics"""
    total_voters = db.query(func.count(PollingVoter.id)).scalar() or 0
    total_municipalities = db.query(func.count(func.distinct(PollingVoter.municipality))).scalar() or 0
    total_stations = db.query(func.count(func.distinct(PollingVoter.polling_station_no))).scalar() or 0
    
    # Gender stats
    male_count = db.query(func.count(PollingVoter.id)).filter(
        func.lower(PollingVoter.gender) == 'male'
    ).scalar() or 0
    
    female_count = db.query(func.count(PollingVoter.id)).filter(
        func.lower(PollingVoter.gender) == 'female'
    ).scalar() or 0
    
    other_count = total_voters - (male_count + female_count)
    
    # Age stats
    age_18_25 = db.query(func.count(PollingVoter.id)).filter(
        PollingVoter.age.between(18, 25)
    ).scalar() or 0
    
    age_26_35 = db.query(func.count(PollingVoter.id)).filter(
        PollingVoter.age.between(26, 35)
    ).scalar() or 0
    
    age_36_50 = db.query(func.count(PollingVoter.id)).filter(
        PollingVoter.age.between(36, 50)
    ).scalar() or 0
    
    age_51_65 = db.query(func.count(PollingVoter.id)).filter(
        PollingVoter.age.between(51, 65)
    ).scalar() or 0
    
    age_65_plus = db.query(func.count(PollingVoter.id)).filter(
        PollingVoter.age >= 66
    ).scalar() or 0
    
    return {
        "success": True,
        "total_voters": total_voters,
        "total_municipalities": total_municipalities,
        "total_polling_stations": total_stations,
        "male_count": male_count,
        "female_count": female_count,
        "other_count": other_count,
        "age_18_25": age_18_25,
        "age_26_35": age_26_35,
        "age_36_50": age_36_50,
        "age_51_65": age_51_65,
        "age_65_plus": age_65_plus,
    }