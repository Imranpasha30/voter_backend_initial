from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.services.polling_voter_service import PollingVoterService
from app.schemas.polling_voter import (
    PollingVoterResponse,
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
    """
    Upload CSV file and import polling voter data
    Only accessible via Swagger/backend
    """
    logger.info(f"📤 CSV Upload by user: {current_user.full_name}")
    
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are allowed"
        )
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Import data
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
    """
    Get list of all municipalities with voter counts
    """
    municipalities = PollingVoterService.get_municipalities(db)
    return municipalities


@router.get("/polling-stations", response_model=List[PollingStationResponse])
def get_polling_stations(
    municipality: str = Query(..., description="Municipality name"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get polling stations for a specific municipality
    """
    stations = PollingVoterService.get_polling_stations(db, municipality)
    return stations


@router.get("/voters")  # ✅ REMOVED response_model=dict
def get_voters(
    municipality: str = Query(..., description="Municipality name"),
    polling_station_no: str = Query(..., description="Polling station number"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get voters for a specific polling station with pagination
    """
    skip = (page - 1) * page_size
    result = PollingVoterService.get_voters_by_polling_station(
        db, municipality, polling_station_no, skip, page_size
    )
    
    # ✅ Convert SQLAlchemy models to dicts
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
    """
    Get detailed information for a specific voter
    """
    voter = PollingVoterService.get_voter_by_id(db, voter_id)
    
    if not voter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voter with ID {voter_id} not found"
        )
    
    return voter


@router.get("/search")  # ✅ REMOVED response_model=dict
def search_voters(
    query: str = Query(..., min_length=1, description="Search query"),
    municipality: Optional[str] = Query(None, description="Filter by municipality"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search voters by name or voter ID
    """
    skip = (page - 1) * page_size
    result = PollingVoterService.search_voters(
        db, query, municipality, skip, page_size
    )
    
    # ✅ Convert SQLAlchemy models to dicts
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


@router.get("/stats")  # ✅ REMOVED response_model=dict
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get overall statistics
    """
    from app.models.polling_voter import PollingVoter
    from sqlalchemy import func
    
    total_voters = db.query(func.count(PollingVoter.id)).scalar()
    total_municipalities = db.query(func.count(func.distinct(PollingVoter.municipality))).scalar()
    total_stations = db.query(func.count(func.distinct(PollingVoter.polling_station_no))).scalar()
    
    return {
        "success": True,
        "total_voters": total_voters or 0,
        "total_municipalities": total_municipalities or 0,
        "total_polling_stations": total_stations or 0
    }
