from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    Query,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, Dict, List
import pandas as pd
import io

from app.db.session import get_db
from app.models.area import Area
from app.models.user_area import UserArea
from app.models.part import Part
from app.models.voter import Voter
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()

CHUNK_SIZE = 500  # Reduced for better memory management


# ========================================
# UPDATE EXISTING AREA WITH LANGUAGE FILE
# ========================================

@router.post("/update-area-language", response_model=dict)
async def update_area_language(
    area_id: int = Form(..., description="Existing area ID to update"),
    language: str = Form(..., description="Language of this file: 'te' or 'en'"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing area with additional language data.
    
    This endpoint allows you to:
    - Upload English file after Telugu file (fills _en columns)
    - Upload Telugu file after English file (fills base columns)
    - Re-upload to update NULL columns with new data
    
    Only updates NULL columns - does not overwrite existing data.
    
    Expected header (any case is OK):
      Voter_ID, Ward_No, District, Municipality, Polling_Station_No,
      Polling_Station_Location, Serial_No, Voter_Name, Relation_Name,
      Age, Gender, House_No, EPIC_No, Date_Time
    """

    language = language.lower()
    if language not in ("te", "en"):
        raise HTTPException(status_code=400, detail="language must be 'te' or 'en'")

    filename = file.filename.lower()
    if not filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Use .csv, .xlsx or .xls",
        )

    try:
        # Check if area exists and user has access
        area = db.query(Area).filter(Area.area_id == area_id).first()
        if not area:
            raise HTTPException(status_code=404, detail="Area not found")

        # Check if user has access to this area
        user_area = (
            db.query(UserArea)
            .filter(
                UserArea.area_id == area_id,
                UserArea.user_id == current_user.user_id,
            )
            .first()
        )

        if not user_area and area.uploaded_by != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this area",
            )

        # Read and validate file
        contents = await file.read()

        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))

        # Normalize column names
        df.columns = [str(col).upper().strip() for col in df.columns]
        df = df.fillna("")

        cols = set(df.columns)

        # Validate required columns
        if "EPIC_NO" not in cols and "VOTER_ID" not in cols:
            raise HTTPException(
                status_code=400,
                detail="Missing required column: EPIC_No or Voter_ID",
            )

        required_base = [
            "POLLING_STATION_NO",
            "POLLING_STATION_LOCATION",
            "VOTER_NAME",
        ]
        missing = [col for col in required_base if col not in cols]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing)}",
            )

        # Process the update
        importer = VoterImporter(db, area.area_id, language=language)
        stats = await importer.process_dataframe(df)

        # Update area metadata
        old_filename = area.file_name or ""
        if language == "te":
            if "+" in old_filename:
                # Already has both files
                parts = old_filename.split("+")
                area.file_name = f"{file.filename} + {parts[1].strip()}"
            else:
                # Add Telugu file
                area.file_name = f"{file.filename} + {old_filename}"
        else:
            if "+" in old_filename:
                # Already has both files
                parts = old_filename.split("+")
                area.file_name = f"{parts[0].strip()} + {file.filename}"
            else:
                # Add English file
                area.file_name = f"{old_filename} + {file.filename}"

        # Update voter count
        area.total_voters = (
            db.query(Voter)
            .join(Part)
            .filter(Part.area_id == area.area_id)
            .count()
        )

        db.commit()

        return {
            "message": f"{language.upper()} file uploaded successfully ✅",
            "area_id": area.area_id,
            "area_name": area.area_name,
            "language": language,
            "stats": stats,
            "total_voters": area.total_voters,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Update failed: {str(e)}"
        )


# ========================================
# SINGLE-LANGUAGE UPLOAD (Telugu or English)
# ========================================

@router.post("/upload", response_model=dict)
async def upload_excel(
    area_name: str = Form(..., description="Geographic area name"),
    description: Optional[str] = Form(None),
    language: str = Form("te", description="Language of this file: 'te' or 'en'"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload CSV/Excel file with voter data (single language).

    language='te' -> values are Telugu, fill base columns and part_name_v1.
    language='en' -> values are English, fill *_en columns and part_name_en.

    Expected header (any case is OK):
      Voter_ID, Ward_No, District, Municipality, Polling_Station_No,
      Polling_Station_Location, Serial_No, Voter_Name, Relation_Name,
      Age, Gender, House_No, EPIC_No, Date_Time
    """

    language = language.lower()
    if language not in ("te", "en"):
        raise HTTPException(status_code=400, detail="language must be 'te' or 'en'")

    filename = file.filename.lower()
    if not filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Use .csv, .xlsx or .xls",
        )

    try:
        contents = await file.read()

        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))

        # Normalize column names for case-insensitive matching
        df.columns = [str(col).upper().strip() for col in df.columns]
        df = df.fillna("")

        cols = set(df.columns)

        # EPIC column can be either EPIC_NO or VOTER_ID
        if "EPIC_NO" not in cols and "VOTER_ID" not in cols:
            raise HTTPException(
                status_code=400,
                detail="Missing required column: EPIC_No or Voter_ID",
            )

        required_base = [
            "POLLING_STATION_NO",
            "POLLING_STATION_LOCATION",
            "VOTER_NAME",
        ]
        missing = [col for col in required_base if col not in cols]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing)}",
            )

        # Create Area record
        area = Area(
            area_name=area_name,
            description=description,
            uploaded_by=current_user.user_id,
            file_name=file.filename,
            total_voters=0,
        )
        db.add(area)
        db.flush()

        # Auto-assign area to uploader
        user_area = UserArea(user_id=current_user.user_id, area_id=area.area_id)
        db.add(user_area)
        db.flush()

        importer = VoterImporter(db, area.area_id, language=language)
        stats = await importer.process_dataframe(df)

        # Count unique voters in this area
        area.total_voters = (
            db.query(Voter)
            .join(Part)
            .filter(Part.area_id == area.area_id)
            .count()
        )
        db.commit()

        return {
            "message": "File uploaded successfully ✅",
            "area_id": area.area_id,
            "area_name": area_name,
            "language": language,
            "stats": stats,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ========================================
# BILINGUAL UPLOAD (Telugu + English together)
# ========================================

@router.post("/upload-bilingual", response_model=dict)
async def upload_bilingual_excel(
    area_name: str = Form(...),
    description: Optional[str] = Form(None),
    telugu_file: UploadFile = File(..., description="Telugu CSV/Excel"),
    english_file: UploadFile = File(..., description="English CSV/Excel"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload Telugu and English files together.

    Both files must have same structure and header:
      Voter_ID, Ward_No, District, Municipality, Polling_Station_No,
      Polling_Station_Location, Serial_No, Voter_Name, Relation_Name,
      Age, Gender, House_No, EPIC_No, Date_Time

    Voters are matched by EPIC_No/Voter_ID; Telugu fills base columns + part_name_v1,
    English fills *_en columns + part_name_en.
    """

    def read_df(upload: UploadFile) -> pd.DataFrame:
        name = upload.filename.lower()
        if not name.endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {upload.filename}",
            )
        data = upload.file.read()
        if name.endswith(".csv"):
            df_local = pd.read_csv(io.BytesIO(data))
        else:
            df_local = pd.read_excel(io.BytesIO(data))
        df_local.columns = [str(col).upper().strip() for col in df_local.columns]
        df_local = df_local.fillna("")
        return df_local

    try:
        df_te = read_df(telugu_file)
        df_en = read_df(english_file)

        for label, df_local in (("telugu", df_te), ("english", df_en)):
            cols = set(df_local.columns)
            if "EPIC_NO" not in cols and "VOTER_ID" not in cols:
                raise HTTPException(
                    status_code=400,
                    detail=f"{label} file missing EPIC_No or Voter_ID",
                )
            required_base = [
                "POLLING_STATION_NO",
                "POLLING_STATION_LOCATION",
                "VOTER_NAME",
            ]
            missing = [c for c in required_base if c not in cols]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"{label} file missing required columns: {', '.join(missing)}",
                )

        # Create Area once
        area = Area(
            area_name=area_name,
            description=description,
            uploaded_by=current_user.user_id,
            file_name=f"{telugu_file.filename} + {english_file.filename}",
            total_voters=0,
        )
        db.add(area)
        db.flush()

        user_area = UserArea(user_id=current_user.user_id, area_id=area.area_id)
        db.add(user_area)
        db.flush()

        # Process Telugu file first (creates base records)
        importer_te = VoterImporter(db, area.area_id, language="te")
        stats_te = await importer_te.process_dataframe(df_te)

        # Process English file second (updates existing records)
        importer_en = VoterImporter(db, area.area_id, language="en")
        stats_en = await importer_en.process_dataframe(df_en)

        # Count unique voters
        area.total_voters = (
            db.query(Voter)
            .join(Part)
            .filter(Part.area_id == area.area_id)
            .count()
        )
        db.commit()

        return {
            "message": "Bilingual files uploaded successfully ✅",
            "area_id": area.area_id,
            "area_name": area_name,
            "stats_telugu": stats_te,
            "stats_english": stats_en,
            "total_unique_voters": area.total_voters,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Bilingual upload failed: {str(e)}")


# ========================================
# VOTER IMPORTER CLASS (COMPLETELY FIXED)
# ========================================

class VoterImporter:
    def __init__(self, db: Session, area_id: int, language: str):
        self.db = db
        self.area_id = area_id
        self.language = language  # "te" or "en"
        self.part_cache: Dict[int, int] = {}

    async def process_dataframe(self, df: pd.DataFrame) -> dict:
        stats = {
            "total_rows": len(df),
            "parts_created": 0,
            "voters_added": 0,
            "voters_updated": 0,
            "skipped": 0,
            "errors_count": 0,
            "errors": [],
        }

        # Process in batches
        batch_voters = []
        processed_epics = set()

        for idx, row in df.iterrows():
            try:
                parsed_data = self._parse_row(row)

                if not parsed_data:
                    stats["errors_count"] += 1
                    stats["skipped"] += 1
                    continue

                epic_no = parsed_data["epic_no"]
                
                # Skip duplicates within the file
                if epic_no in processed_epics:
                    stats["skipped"] += 1
                    continue

                processed_epics.add(epic_no)
                batch_voters.append(parsed_data)

                # Process in batches
                if len(batch_voters) >= CHUNK_SIZE:
                    self._process_batch(batch_voters, stats)
                    batch_voters.clear()

            except Exception as e:
                stats["errors"].append(f"Row {idx + 2}: {str(e)}")
                stats["errors_count"] += 1

        # Process remaining
        if batch_voters:
            self._process_batch(batch_voters, stats)

        stats["parts_created"] = len(self.part_cache)
        return stats

    def _process_batch(self, batch_voters: List[dict], stats: dict):
        """Process a batch of voters"""
        
        # Get all EPICs in this batch
        epic_nos = [v["epic_no"] for v in batch_voters]
        
        # Fetch all existing voters in one query
        existing_voters = (
            self.db.query(Voter)
            .filter(Voter.epic_no.in_(epic_nos))
            .all()
        )
        
        existing_epics = {v.epic_no: v for v in existing_voters}
        
        voters_to_insert = []
        voters_to_update = []

        for voter_data in batch_voters:
            epic_no = voter_data["epic_no"]
            
            if epic_no not in existing_epics:
                # New voter - insert
                voters_to_insert.append(Voter(**voter_data["data"]))
            else:
                # Existing voter - update
                voters_to_update.append({
                    "voter": existing_epics[epic_no],
                    "updates": voter_data["data"]
                })

        # Bulk insert new voters
        if voters_to_insert:
            self.db.bulk_save_objects(voters_to_insert)
            stats["voters_added"] += len(voters_to_insert)

        # Update existing voters
        for update_item in voters_to_update:
            voter = update_item["voter"]
            updates = update_item["updates"]
            
            for key, value in updates.items():
                if value is not None:
                    setattr(voter, key, value)
            
            stats["voters_updated"] += 1

        self.db.flush()

    def _parse_row(self, row) -> Optional[dict]:
        """Parse row and return structured data"""
        
        def get_str(key: str) -> Optional[str]:
            val = row.get(key, "")
            if pd.isna(val) or str(val).strip() == "":
                return None
            return str(val).strip()

        def get_int(key: str) -> Optional[int]:
            val = row.get(key, "")
            if pd.isna(val) or str(val).strip() == "":
                return None
            try:
                return int(float(val))
            except:
                return None

        # EPIC / Voter ID
        epic_no = get_str("EPIC_NO") or get_str("VOTER_ID")
        if not epic_no:
            return None

        # Polling station number
        polling_station_no = get_int("POLLING_STATION_NO")
        if not polling_station_no:
            return None

        # Extract all fields
        district_val = get_str("DISTRICT")
        municipality_val = get_str("MUNICIPALITY")
        ps_location_val = get_str("POLLING_STATION_LOCATION")
        voter_name_val = get_str("VOTER_NAME")
        relation_name_val = get_str("RELATION_NAME")
        ward_no_val = get_str("WARD_NO")
        serial_no_val = get_str("SERIAL_NO")
        house_no_val = get_str("HOUSE_NO")
        age_val = get_int("AGE")
        gender_val = get_str("GENDER")
        date_time_val = get_str("DATE_TIME")

        if not voter_name_val:
            return None

        # Get or create part
        part_id = self._get_or_create_part(
            part_no=polling_station_no,
            ps_location_value=ps_location_val,
        )

        # Build voter data based on whether it exists
        existing_voter = (
            self.db.query(Voter)
            .filter(Voter.epic_no == epic_no)
            .first()
        )

        if not existing_voter:
            # NEW VOTER
            voter_data = {
                "epic_no": epic_no,
                "part_id": part_id,
                "ward_no": ward_no_val,
                "polling_station_no": str(polling_station_no),
                "serial_no": serial_no_val,
                "age": age_val,
                "gender": gender_val,
                "house_no": house_no_val,
                "date_time": date_time_val,
            }

            if self.language == "te":
                # Telugu: fill base columns, leave _en as NULL
                voter_data.update({
                    "district": district_val,
                    "municipality": municipality_val,
                    "polling_station_location": ps_location_val,
                    "voter_name": voter_name_val,
                    "relation_name": relation_name_val,
                })
            else:
                # English: fill both base and _en columns
                voter_data.update({
                    "district": district_val,
                    "municipality": municipality_val,
                    "polling_station_location": ps_location_val,
                    "voter_name": voter_name_val,
                    "relation_name": relation_name_val,
                    "district_en": district_val,
                    "municipality_en": municipality_val,
                    "polling_station_location_en": ps_location_val,
                    "voter_name_en": voter_name_val,
                    "relation_name_en": relation_name_val,
                })

            return {
                "epic_no": epic_no,
                "is_new": True,
                "data": voter_data
            }

        else:
            # EXISTING VOTER - only update NULL columns
            updates = {}

            if self.language == "te":
                # Update Telugu columns only if NULL
                if not existing_voter.district and district_val:
                    updates["district"] = district_val
                if not existing_voter.municipality and municipality_val:
                    updates["municipality"] = municipality_val
                if not existing_voter.polling_station_location and ps_location_val:
                    updates["polling_station_location"] = ps_location_val
                if not existing_voter.voter_name and voter_name_val:
                    updates["voter_name"] = voter_name_val
                if not existing_voter.relation_name and relation_name_val:
                    updates["relation_name"] = relation_name_val
            else:
                # Update English columns only if NULL
                if not existing_voter.district_en and district_val:
                    updates["district_en"] = district_val
                if not existing_voter.municipality_en and municipality_val:
                    updates["municipality_en"] = municipality_val
                if not existing_voter.polling_station_location_en and ps_location_val:
                    updates["polling_station_location_en"] = ps_location_val
                if not existing_voter.voter_name_en and voter_name_val:
                    updates["voter_name_en"] = voter_name_val
                if not existing_voter.relation_name_en and relation_name_val:
                    updates["relation_name_en"] = relation_name_val

            return {
                "epic_no": epic_no,
                "is_new": False,
                "data": updates
            }

    def _get_or_create_part(
        self,
        part_no: int,
        ps_location_value: Optional[str],
    ) -> int:
        """
        Get existing part or create/update it with language-specific names.
        
        - part_name_en  -> English Polling_Station_Location
        - part_name_v1  -> Telugu Polling_Station_Location
        """
        if part_no in self.part_cache:
            return self.part_cache[part_no]

        # Check if part exists in current area
        part = (
            self.db.query(Part)
            .filter(Part.part_no == part_no, Part.area_id == self.area_id)
            .first()
        )

        if part:
            # Existing part: update the appropriate language field if NULL
            if self.language == "te":
                if not part.part_name_v1 and ps_location_value:
                    part.part_name_v1 = ps_location_value
            else:
                if not part.part_name_en and ps_location_value:
                    part.part_name_en = ps_location_value
            
            self.db.flush()
            part_id = part.part_id
        else:
            # New part: create with language-specific field
            if self.language == "te":
                part = Part(
                    part_no=part_no,
                    area_id=self.area_id,
                    part_name_v1=ps_location_value,  # Telugu
                    part_name_en=None,
                )
            else:
                part = Part(
                    part_no=part_no,
                    area_id=self.area_id,
                    part_name_en=ps_location_value,  # English
                    part_name_v1=None,
                )

            self.db.add(part)
            self.db.flush()
            part_id = part.part_id

        self.part_cache[part_no] = part_id
        return part_id


# ========================================
# USER ACCESS MANAGEMENT
# ========================================

@router.post("/assign-access", response_model=dict)
def assign_users_to_area(
    area_id: int = Form(...),
    user_emails: str = Form(..., description="Comma-separated emails"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign multiple users by email (comma-separated)."""

    area = db.query(Area).filter(Area.area_id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")

    if area.uploaded_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Only uploader can assign access")

    email_list = [email.strip().lower() for email in user_emails.split(",") if email.strip()]

    if not email_list:
        raise HTTPException(status_code=400, detail="No emails provided")

    users = db.query(User).filter(User.email.in_(email_list)).all()
    found_emails = {u.email.lower() for u in users}
    invalid_emails = set(email_list) - found_emails

    if invalid_emails:
        raise HTTPException(
            status_code=404,
            detail=f"Users not found: {', '.join(invalid_emails)}",
        )

    already_assigned = (
        db.query(UserArea)
        .filter(
            UserArea.area_id == area_id,
            UserArea.user_id.in_([u.user_id for u in users]),
        )
        .all()
    )
    already_assigned_ids = {ua.user_id for ua in already_assigned}

    newly_assigned_details = []
    for user in users:
        if user.user_id not in already_assigned_ids:
            user_area = UserArea(user_id=user.user_id, area_id=area_id)
            db.add(user_area)
            newly_assigned_details.append(
                {
                    "user_id": user.user_id,
                    "email": user.email,
                    "full_name": user.full_name,
                }
            )

    db.commit()

    return {
        "message": "Access assigned ✅",
        "area_id": area_id,
        "area_name": area.area_name,
        "newly_assigned": newly_assigned_details,
        "already_had_access": len(already_assigned_ids),
    }


@router.get("/search-users")
def search_users_for_assignment(
    query: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search users by name/email for dropdown."""

    search_pattern = f"%{query}%"

    users = (
        db.query(User)
        .filter(
            or_(
                User.email.ilike(search_pattern),
                User.full_name.ilike(search_pattern),
            ),
            User.is_active == True,
        )
        .limit(limit)
        .all()
    )

    return {
        "query": query,
        "count": len(users),
        "users": [
            {
                "user_id": u.user_id,
                "email": u.email,
                "full_name": u.full_name or "N/A",
                "display_name": f"{u.full_name or 'N/A'} ({u.email})",
            }
            for u in users
        ],
    }


@router.get("/area-users/{area_id}")
def get_area_assigned_users(
    area_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all users with access to area."""

    area = db.query(Area).filter(Area.area_id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")

    user_area = (
        db.query(UserArea)
        .filter(
            UserArea.area_id == area_id,
            UserArea.user_id == current_user.user_id,
        )
        .first()
    )

    if not user_area and area.uploaded_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")

    user_areas = db.query(UserArea).filter(UserArea.area_id == area_id).all()
    user_ids = [ua.user_id for ua in user_areas]
    users = db.query(User).filter(User.user_id.in_(user_ids)).all()

    return {
        "area_id": area_id,
        "area_name": area.area_name,
        "total_users": len(users),
        "users": [
            {
                "user_id": u.user_id,
                "email": u.email,
                "full_name": u.full_name,
                "is_uploader": u.user_id == area.uploaded_by,
            }
            for u in users
        ],
    }


@router.delete("/revoke-access")
def revoke_user_access(
    area_id: int = Form(...),
    user_id: int = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke user access (cannot revoke uploader)."""

    area = db.query(Area).filter(Area.area_id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")

    if area.uploaded_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Only uploader can revoke")

    if user_id == area.uploaded_by:
        raise HTTPException(status_code=400, detail="Cannot revoke uploader access")

    user_area = (
        db.query(UserArea)
        .filter(UserArea.area_id == area_id, UserArea.user_id == user_id)
        .first()
    )

    if not user_area:
        raise HTTPException(status_code=404, detail="User access not found")

    db.delete(user_area)
    db.commit()

    return {"message": "Access revoked"}


@router.get("/area-language-status/{area_id}")
def get_area_language_status(
    area_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check which language data is available for an area.
    
    Returns:
    - has_telugu: boolean indicating if Telugu data exists
    - has_english: boolean indicating if English data exists
    - sample_voters: sample of voters showing data availability
    """

    # Check if area exists and user has access
    area = db.query(Area).filter(Area.area_id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")

    user_area = (
        db.query(UserArea)
        .filter(
            UserArea.area_id == area_id,
            UserArea.user_id == current_user.user_id,
        )
        .first()
    )

    if not user_area and area.uploaded_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get sample voters from this area
    sample_voters = (
        db.query(Voter)
        .join(Part)
        .filter(Part.area_id == area_id)
        .limit(10)
        .all()
    )

    if not sample_voters:
        return {
            "area_id": area_id,
            "area_name": area.area_name,
            "has_telugu": False,
            "has_english": False,
            "total_voters": 0,
            "message": "No voters found in this area",
        }

    # Check language availability
    has_telugu = any(
        v.voter_name or v.district or v.municipality or v.polling_station_location
        for v in sample_voters
    )
    
    has_english = any(
        v.voter_name_en or v.district_en or v.municipality_en or v.polling_station_location_en
        for v in sample_voters
    )

    # Count how many voters have each language
    telugu_count = sum(
        1 for v in sample_voters
        if v.voter_name or v.district or v.municipality
    )
    
    english_count = sum(
        1 for v in sample_voters
        if v.voter_name_en or v.district_en or v.municipality_en
    )

    return {
        "area_id": area_id,
        "area_name": area.area_name,
        "total_voters": area.total_voters,
        "has_telugu": has_telugu,
        "has_english": has_english,
        "telugu_coverage": f"{telugu_count}/{len(sample_voters)} in sample",
        "english_coverage": f"{english_count}/{len(sample_voters)} in sample",
        "file_name": area.file_name,
        "recommendation": (
            "Area has both languages ✅" if has_telugu and has_english
            else "Upload English file to add translations" if has_telugu and not has_english
            else "Upload Telugu file to add translations" if has_english and not has_telugu
            else "No language data available"
        ),
    }


@router.get("/my-areas")
def get_my_accessible_areas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all areas accessible to current user."""

    user_areas = (
        db.query(UserArea.area_id)
        .filter(UserArea.user_id == current_user.user_id)
        .all()
    )
    area_ids = [ua.area_id for ua in user_areas]

    if not area_ids:
        return {"total": 0, "page": page, "page_size": page_size, "areas": []}

    query = db.query(Area).filter(Area.area_id.in_(area_ids))
    total = query.count()

    offset = (page - 1) * page_size
    areas = (
        query.order_by(Area.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "areas": [
            {
                "area_id": a.area_id,
                "area_name": a.area_name,
                "total_voters": a.total_voters,
                "is_uploader": a.uploaded_by == current_user.user_id,
                "upload_date": a.upload_date,
            }
            for a in areas
        ],
    }


# ========================================
# VALIDATION & TEMPLATE
# ========================================

@router.post("/validate")
async def validate_excel(file: UploadFile = File(...)):
    """Validate CSV/Excel before upload."""

    filename = file.filename.lower()
    if not filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Invalid file type")

    try:
        contents = await file.read()

        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))

        original_columns = df.columns.tolist()
        df.columns = [str(col).upper().strip() for col in df.columns]

        cols = set(df.columns)

        epic_ok = "EPIC_NO" in cols or "VOTER_ID" in cols
        required_base = [
            "POLLING_STATION_NO",
            "POLLING_STATION_LOCATION",
            "VOTER_NAME",
        ]
        missing_base = [col for col in required_base if col not in cols]

        missing = []
        if not epic_ok:
            missing.append("EPIC_No or Voter_ID")
        missing.extend(missing_base)

        return {
            "valid": len(missing) == 0,
            "total_rows": len(df),
            "columns": original_columns,
            "missing": missing,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation failed: {str(e)}")


@router.get("/template")
def download_template():
    """
    Download Excel template for a single-language voter file.

    Header (exact names, case-insensitive on upload):
      Voter_ID, Ward_No, District, Municipality, Polling_Station_No,
      Polling_Station_Location, Serial_No, Voter_Name, Relation_Name,
      Age, Gender, House_No, EPIC_No, Date_Time
    """

    sample = {
        "Voter_ID": ["IXR2457125", "IXR3160199"],
        "Ward_No": [17, 17],
        "District": ["Mahabubnagar", "Mahabubnagar"],
        "Municipality": ["Mahabubnagar MC", "Mahabubnagar MC"],
        "Polling_Station_No": [75, 75],
        "Polling_Station_Location": [
            "Government high school Mothinagar 6 th Class T/M",
            "Government high school Mothinagar 6 th Class T/M",
        ],
        "Serial_No": [477, 478],
        "Voter_Name": ["Jamulamma", "MOHAMMED FAYAZ"],
        "Relation_Name": ["Shiva", "MOHD ABBAS ALI"],
        "Age": [42, 19],
        "Gender": ["Female", "Male"],
        "House_No": ["1-1-70", "1-1-74/A"],
        "EPIC_No": ["IXR2457125", "IXR3160199"],
        "Date_Time": [
            "11-02-2026 & 7AM TO 5PM",
            "11-02-2026 & 7AM TO 5PM",
        ],
    }

    df = pd.DataFrame(sample)
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Voters")

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=voter_template.xlsx"
        },
    )