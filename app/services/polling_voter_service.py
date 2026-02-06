import csv
import io
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, or_, cast, Integer
from app.models.polling_voter import PollingVoter
from app.schemas.polling_voter import PollingVoterCreate
import logging

logger = logging.getLogger(__name__)


class PollingVoterService:
    
    @staticmethod
    def import_from_csv(db: Session, csv_content: str) -> Dict:
        """
        Import voters from CSV content
        Handles both EPIC_No and Voter_ID columns (uses whichever is present)
        """
        try:
            # Parse CSV
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
            
            total_rows = 0
            imported_rows = 0
            skipped_rows = 0
            errors = []
            
            for row in reader:
                total_rows += 1
                
                try:
                    # Handle both EPIC_No and Voter_ID
                    voter_id = row.get('EPIC_No') or row.get('Voter_ID') or row.get('epic_no') or row.get('voter_id')
                    
                    if not voter_id or not voter_id.strip():
                        skipped_rows += 1
                        errors.append(f"Row {total_rows}: Missing voter ID")
                        continue
                    
                    voter_id = voter_id.strip()
                    
                    # Check if voter already exists
                    existing = db.query(PollingVoter).filter(
                        PollingVoter.voter_id == voter_id
                    ).first()
                    
                    if existing:
                        skipped_rows += 1
                        logger.debug(f"Skipping duplicate voter: {voter_id}")
                        continue
                    
                    # Get municipality (required field)
                    municipality = row.get('Municipality') or row.get('municipality')
                    polling_station_no = row.get('Polling_Station_No') or row.get('polling_station_no')
                    
                    if not municipality or not polling_station_no:
                        skipped_rows += 1
                        errors.append(f"Row {total_rows}: Missing municipality or polling station")
                        continue
                    
                    # Create new voter
                    voter = PollingVoter(
                        voter_id=voter_id,
                        ward_no=row.get('Ward_No') or row.get('ward_no'),
                        district=row.get('District') or row.get('district'),
                        municipality=municipality.strip(),
                        polling_station_no=polling_station_no.strip(),
                        polling_station_location=row.get('Polling_Station_Location') or row.get('polling_station_location'),
                        serial_no=row.get('Serial_No') or row.get('serial_no'),
                        voter_name=row.get('Voter_Name') or row.get('voter_name'),
                        relation_name=row.get('Relation_Name') or row.get('relation_name'),
                        age=int(row.get('Age') or row.get('age')) if (row.get('Age') or row.get('age', '')).strip().isdigit() else None,
                        gender=row.get('Gender') or row.get('gender'),
                        house_no=row.get('House_No') or row.get('house_no'),
                        date_time=row.get('Date_Time') or row.get('date_time'),
                    )
                    
                    db.add(voter)
                    imported_rows += 1
                    
                    # Commit in batches of 100
                    if imported_rows % 100 == 0:
                        db.commit()
                        logger.info(f"✅ Imported {imported_rows} voters...")
                
                except Exception as e:
                    skipped_rows += 1
                    errors.append(f"Row {total_rows}: {str(e)}")
                    logger.error(f"Error processing row {total_rows}: {str(e)}")
                    continue
            
            # Final commit
            db.commit()
            
            logger.info(f"✅ CSV Import Complete: {imported_rows}/{total_rows} imported")
            
            return {
                "success": True,
                "message": "CSV imported successfully",
                "total_rows": total_rows,
                "imported_rows": imported_rows,
                "skipped_rows": skipped_rows,
                "errors": errors[:10]  # Return first 10 errors only
            }
        
        except Exception as e:
            db.rollback()
            logger.exception("❌ CSV import failed")
            return {
                "success": False,
                "message": f"Import failed: {str(e)}",
                "total_rows": 0,
                "imported_rows": 0,
                "skipped_rows": 0,
                "errors": [str(e)]
            }
    
    @staticmethod
    def get_municipalities(db: Session) -> List[Dict]:
        """
        Get unique municipalities with voter counts
        """
        results = db.query(
            PollingVoter.municipality,
            func.count(PollingVoter.id).label('voter_count')
        ).group_by(
            PollingVoter.municipality
        ).order_by(
            PollingVoter.municipality
        ).all()
        
        return [
            {
                "municipality": r.municipality,
                "voter_count": r.voter_count
            }
            for r in results
        ]
    
    @staticmethod
    def get_polling_stations(db: Session, municipality: str) -> List[Dict]:
        """
        Get polling stations for a specific municipality
        """
        results = db.query(
            PollingVoter.polling_station_no,
            PollingVoter.polling_station_location,
            func.count(PollingVoter.id).label('voter_count')
        ).filter(
            PollingVoter.municipality == municipality
        ).group_by(
            PollingVoter.polling_station_no,
            PollingVoter.polling_station_location
        ).order_by(
            cast(PollingVoter.polling_station_no, Integer).asc()
        ).all()
        
        return [
            {
                "polling_station_no": r.polling_station_no,
                "polling_station_location": r.polling_station_location,
                "voter_count": r.voter_count
            }
            for r in results
        ]
    
    @staticmethod
    def get_voters_by_polling_station(
        db: Session,
        municipality: str,
        polling_station_no: str,
        skip: int = 0,
        limit: int = 50
    ) -> Dict:
        """
        Get voters for a specific polling station with pagination
        """
        query = db.query(PollingVoter).filter(
            PollingVoter.municipality == municipality,
            PollingVoter.polling_station_no == polling_station_no
        ).order_by(
            cast(PollingVoter.serial_no, Integer).asc().nullslast()
        )
        
        total = query.count()
        voters = query.offset(skip).limit(limit).all()
        
        return {
            "voters": voters,
            "total": total,
            "page": (skip // limit) + 1,
            "page_size": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 1
        }
    
    @staticmethod
    def get_voter_by_id(db: Session, voter_id: str) -> Optional[PollingVoter]:
        """
        Get single voter by EPIC_No
        """
        return db.query(PollingVoter).filter(
            PollingVoter.voter_id == voter_id
        ).first()
    
    @staticmethod
    def search_voters(
        db: Session,
        query: str,
        municipality: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Dict:
        """
        Search voters by name or voter ID
        """
        search_query = db.query(PollingVoter)
        
        if municipality:
            search_query = search_query.filter(
                PollingVoter.municipality == municipality
            )
        
        search_query = search_query.filter(
            or_(
                PollingVoter.voter_name.ilike(f"%{query}%"),
                PollingVoter.voter_id.ilike(f"%{query}%")
            )
        )
        
        total = search_query.count()
        voters = search_query.offset(skip).limit(limit).all()
        
        return {
            "voters": voters,
            "total": total,
            "page": (skip // limit) + 1,
            "page_size": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 1
        }
