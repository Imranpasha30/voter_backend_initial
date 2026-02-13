import csv
from io import StringIO
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.polling_voter import PollingVoter
from app.schemas.polling_voter import MunicipalityResponse, PollingStationResponse
import logging

logger = logging.getLogger(__name__)


class PollingVoterService:
    
    @staticmethod
    def import_from_csv(db: Session, csv_content: str) -> dict:
        """
        Import polling voter data from CSV with PDF URLs
        Handles both snake_case and Title_Case column names
        """
        csv_file = StringIO(csv_content)
        csv_reader = csv.DictReader(csv_file)
        
        total_rows = 0
        imported_rows = 0
        skipped_rows = 0
        errors = []
        
        headers = csv_reader.fieldnames
        logger.info(f"📋 CSV Headers: {headers}")
        
        for row_num, row in enumerate(csv_reader, start=2):
            total_rows += 1
            
            try:
                voter_id = (
                    row.get('Voter_ID') or 
                    row.get('voter_id') or 
                    row.get('VOTER_ID') or 
                    row.get('VoterID') or
                    ''
                ).strip()
                
                if not voter_id:
                    skipped_rows += 1
                    errors.append(f"Row {row_num}: Missing Voter_ID")
                    continue
                
                existing_voter = db.query(PollingVoter).filter(
                    PollingVoter.voter_id == voter_id
                ).first()
                
                pdf_url = f"https://ik.imagekit.io/rokudigitals/VoterConnectImages/VoterCard2/voter_slips_pdf/{voter_id}.pdf"
                
                ward_no = row.get('Ward_No') or row.get('ward_no')
                district = row.get('District') or row.get('district')
                municipality = row.get('Municipality') or row.get('municipality')
                polling_station_no = row.get('Polling_Station_No') or row.get('polling_station_no')
                polling_station_location = row.get('Polling_Station_Location') or row.get('polling_station_location')
                serial_no = row.get('Serial_No') or row.get('serial_no')
                voter_name = row.get('Voter_Name') or row.get('voter_name')
                relation_name = row.get('Relation_Name') or row.get('relation_name')
                age_str = row.get('Age') or row.get('age')
                gender = row.get('Gender') or row.get('gender')
                house_no = row.get('House_No') or row.get('house_no')
                date_time = row.get('Date_Time') or row.get('date_time')
                
                age = None
                if age_str:
                    try:
                        age = int(age_str)
                    except ValueError:
                        pass
                
                if existing_voter:
                    existing_voter.ward_no = ward_no
                    existing_voter.district = district
                    existing_voter.municipality = municipality
                    existing_voter.polling_station_no = polling_station_no
                    existing_voter.polling_station_location = polling_station_location
                    existing_voter.serial_no = serial_no
                    existing_voter.voter_name = voter_name
                    existing_voter.relation_name = relation_name
                    existing_voter.age = age
                    existing_voter.gender = gender
                    existing_voter.house_no = house_no
                    existing_voter.date_time = date_time
                    existing_voter.pdf_url = pdf_url
                else:
                    new_voter = PollingVoter(
                        voter_id=voter_id,
                        ward_no=ward_no,
                        district=district,
                        municipality=municipality,
                        polling_station_no=polling_station_no,
                        polling_station_location=polling_station_location,
                        serial_no=serial_no,
                        voter_name=voter_name,
                        relation_name=relation_name,
                        age=age,
                        gender=gender,
                        house_no=house_no,
                        date_time=date_time,
                        pdf_url=pdf_url
                    )
                    db.add(new_voter)
                
                imported_rows += 1
                
                if imported_rows % 100 == 0:
                    db.commit()
                    logger.info(f"✅ Imported {imported_rows}/{total_rows} voters...")
                
            except Exception as e:
                skipped_rows += 1
                errors.append(f"Row {row_num}: {str(e)}")
                logger.error(f"❌ Error importing row {row_num}: {e}")
        
        db.commit()
        
        logger.info(f"🎉 Import completed: {imported_rows}/{total_rows} voters")
        
        return {
            "success": True,
            "message": f"Successfully imported {imported_rows} voters",
            "total_rows": total_rows,
            "imported_rows": imported_rows,
            "skipped_rows": skipped_rows,
            "errors": errors[:20]
        }
    
    @staticmethod
    def update_phone_numbers_from_csv(db: Session, csv_content: str) -> Dict[str, Any]:
        """
        Update phone numbers from CSV/Excel with EPIC_NO and MOBILE_NO columns
        """
        csv_file = StringIO(csv_content)
        csv_reader = csv.DictReader(csv_file)
        
        total_rows = 0
        updated_rows = 0
        skipped_rows = 0
        not_found_rows = 0
        errors = []
        
        headers = csv_reader.fieldnames
        logger.info(f"📋 Phone CSV Headers: {headers}")
        
        # Identify column names
        epic_col = None
        mobile_col = None
        
        for header in headers:
            header_lower = header.lower().strip()
            if 'epic' in header_lower or 'voter_id' in header_lower or 'voter id' in header_lower:
                epic_col = header
            if 'mobile' in header_lower or 'phone' in header_lower or 'contact' in header_lower:
                mobile_col = header
        
        if not epic_col or not mobile_col:
            raise ValueError(f"Could not find EPIC_NO and MOBILE_NO columns. Found headers: {headers}")
        
        logger.info(f"✅ Using columns - EPIC: '{epic_col}', MOBILE: '{mobile_col}'")
        
        for row_num, row in enumerate(csv_reader, start=2):
            total_rows += 1
            
            try:
                # Get EPIC_NO (voter_id)
                voter_id = str(row.get(epic_col, '')).strip()
                if not voter_id or voter_id.lower() in ['nan', 'none', '']:
                    skipped_rows += 1
                    errors.append(f"Row {row_num}: Missing EPIC_NO")
                    continue
                
                # Get MOBILE_NO
                mobile_no = str(row.get(mobile_col, '')).strip()
                if not mobile_no or mobile_no.lower() in ['nan', 'none', '']:
                    skipped_rows += 1
                    errors.append(f"Row {row_num}: Missing MOBILE_NO for {voter_id}")
                    continue
                
                # Clean mobile number
                mobile_no = mobile_no.replace('+91', '').replace('-', '').replace(' ', '').strip()
                
                # Validate mobile number
                if not mobile_no.isdigit() or len(mobile_no) != 10:
                    skipped_rows += 1
                    errors.append(f"Row {row_num}: Invalid mobile '{mobile_no}' for {voter_id}")
                    continue
                
                # Find voter in database
                voter = db.query(PollingVoter).filter(
                    PollingVoter.voter_id == voter_id
                ).first()
                
                if voter:
                    voter.phone_number = mobile_no
                    updated_rows += 1
                    
                    if updated_rows % 100 == 0:
                        db.commit()
                        logger.info(f"✅ Updated {updated_rows}/{total_rows} phone numbers...")
                else:
                    not_found_rows += 1
                    errors.append(f"Row {row_num}: Voter {voter_id} not found")
            
            except Exception as e:
                skipped_rows += 1
                errors.append(f"Row {row_num}: {str(e)}")
                logger.error(f"❌ Error processing row {row_num}: {e}")
        
        db.commit()
        
        logger.info(f"🎉 Phone update completed: {updated_rows}/{total_rows} voters")
        
        return {
            "success": True,
            "message": f"Successfully updated {updated_rows} phone numbers",
            "total_rows": total_rows,
            "updated_rows": updated_rows,
            "skipped_rows": skipped_rows,
            "not_found_rows": not_found_rows,
            "errors": errors[:50]
        }
    
    @staticmethod
    def get_municipalities(db: Session) -> List[MunicipalityResponse]:
        """Get all unique municipalities with voter counts"""
        results = db.query(
            PollingVoter.municipality,
            func.count(PollingVoter.id).label('voter_count')
        ).group_by(PollingVoter.municipality).order_by(PollingVoter.municipality).all()
        
        return [
            MunicipalityResponse(
                municipality=municipality,
                voter_count=count
            )
            for municipality, count in results
        ]
    
    @staticmethod
    def get_polling_stations(db: Session, municipality: str) -> List[PollingStationResponse]:
        """Get polling stations for a municipality"""
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
            PollingVoter.polling_station_no
        ).all()
        
        return [
            PollingStationResponse(
                polling_station_no=station_no,
                polling_station_location=location,
                voter_count=count
            )
            for station_no, location, count in results
        ]
    
    @staticmethod
    def get_voters_by_polling_station(
        db: Session,
        municipality: str,
        polling_station_no: str,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get voters for a specific polling station with pagination"""
        query = db.query(PollingVoter).filter(
            PollingVoter.municipality == municipality,
            PollingVoter.polling_station_no == polling_station_no
        ).order_by(PollingVoter.serial_no)
        
        total = query.count()
        voters = query.offset(skip).limit(limit).all()
        
        return {
            "voters": voters,
            "total": total,
            "page": (skip // limit) + 1,
            "page_size": limit,
            "total_pages": (total + limit - 1) // limit
        }
    
    @staticmethod
    def get_voter_by_id(db: Session, voter_id: str) -> Optional[PollingVoter]:
        """Get voter by voter ID"""
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
    ) -> Dict[str, Any]:
        """Search voters by name or ID"""
        search_query = db.query(PollingVoter).filter(
            or_(
                PollingVoter.voter_name.ilike(f"%{query}%"),
                PollingVoter.voter_id.ilike(f"%{query}%"),
                PollingVoter.house_no.ilike(f"%{query}%")
            )
        )
        
        if municipality:
            search_query = search_query.filter(
                PollingVoter.municipality == municipality
            )
        
        total = search_query.count()
        voters = search_query.offset(skip).limit(limit).all()
        
        return {
            "voters": voters,
            "total": total,
            "page": (skip // limit) + 1,
            "page_size": limit,
            "total_pages": (total + limit - 1) // limit
        }

    @staticmethod
    def update_voter(
        db: Session,
        voter_id: str,
        phone_number: Optional[str] = None,
        is_voted: Optional[bool] = None,
        voting_status: Optional[str] = None
    ) -> Optional[PollingVoter]:
        """Update voter tracking information"""
        try:
            voter = db.query(PollingVoter).filter(
                PollingVoter.voter_id == voter_id
            ).first()
            
            if not voter:
                return None
            
            if phone_number is not None:
                voter.phone_number = phone_number
            
            if is_voted is not None:
                voter.is_voted = is_voted
            
            if voting_status is not None:
                if voting_status not in ['red', 'yellow', 'green', None, '']:
                    raise ValueError(f"Invalid voting_status: {voting_status}")
                voter.voting_status = voting_status if voting_status else None
            
            db.commit()
            db.refresh(voter)
            
            logger.info(f"✅ Updated voter {voter_id}")
            return voter
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to update voter {voter_id}: {str(e)}")
            raise

    @staticmethod
    def bulk_update_voters(
        db: Session,
        voter_ids: List[str],
        voting_status: Optional[str] = None,
        is_voted: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Bulk update multiple voters"""
        try:
            query = db.query(PollingVoter).filter(
                PollingVoter.voter_id.in_(voter_ids)
            )
            
            update_data = {}
            if voting_status is not None:
                if voting_status not in ['red', 'yellow', 'green']:
                    raise ValueError(f"Invalid voting_status: {voting_status}")
                update_data['voting_status'] = voting_status
            
            if is_voted is not None:
                update_data['is_voted'] = is_voted
            
            if not update_data:
                return {
                    "success": False,
                    "message": "No update data provided",
                    "updated_count": 0
                }
            
            count = query.update(update_data, synchronize_session=False)
            db.commit()
            
            logger.info(f"✅ Bulk updated {count} voters")
            
            return {
                "success": True,
                "message": f"Successfully updated {count} voters",
                "updated_count": count
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Bulk update failed: {str(e)}")
            raise
