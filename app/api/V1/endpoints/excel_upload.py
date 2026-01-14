from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, func
from typing import Optional, Dict, List
import pandas as pd
import io
from datetime import datetime
import asyncio

from app.db.session import get_db
from app.models.area import Area
from app.models.user_area import UserArea
from app.models.part import Part
from app.models.voter import Voter
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()

# Constants
CHUNK_SIZE = 1000

# ========================================
# EXCEL UPLOAD
# ========================================

@router.post("/upload", response_model=dict)
async def upload_excel(
    area_name: str = Form(..., description="Geographic area name"),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload Excel file with voter data"""
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Use .xlsx or .xls")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        df.columns = [col.upper() for col in df.columns]
        
        print(f"📊 Excel loaded: {len(df)} rows, {len(df.columns)} columns")
        
        required = ['PART_NO', 'EPIC_NO']
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing)}"
            )
        
        df = df.fillna('')
        
        area = Area(
            area_name=area_name,
            description=description,
            uploaded_by=current_user.user_id,
            file_name=file.filename,
            total_voters=0
        )
        db.add(area)
        db.flush()
        
        # Auto-assign to uploader
        user_area = UserArea(
            user_id=current_user.user_id,
            area_id=area.area_id
        )
        db.add(user_area)
        db.flush()
        
        importer = VoterImporter(db, area.area_id)
        stats = await importer.process_dataframe(df)
        
        area.total_voters = stats['voters_added'] + stats['voters_updated']
        db.commit()
        
        return {
            "message": "Excel uploaded successfully ✅",
            "area_id": area.area_id,
            "area_name": area_name,
            "stats": stats
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ========================================
# VOTER IMPORTER CLASS
# ========================================

class VoterImporter:
    def __init__(self, db: Session, area_id: int):
        self.db = db
        self.area_id = area_id
        self.part_cache: Dict[int, int] = {}
        self.processed_epics = set()
    
    async def process_dataframe(self, df: pd.DataFrame) -> dict:
        stats = {
            'total_rows': len(df),
            'parts_created': 0,
            'voters_added': 0,
            'voters_updated': 0,
            'errors_count': 0,
            'errors': []
        }
        
        voters_batch = []
        
        for idx, row in df.iterrows():
            try:
                voter_data = self._parse_row(row)
                
                if not voter_data:
                    stats['errors_count'] += 1
                    continue
                
                if voter_data['epic_no'] in self.processed_epics:
                    continue
                
                self.processed_epics.add(voter_data['epic_no'])
                voters_batch.append(voter_data)
                
                if len(voters_batch) >= CHUNK_SIZE:
                    inserted, updated = self._insert_batch(voters_batch)
                    stats['voters_added'] += inserted
                    stats['voters_updated'] += updated
                    voters_batch.clear()
            
            except Exception as e:
                stats['errors'].append(f"Row {idx + 2}: {str(e)}")
                stats['errors_count'] += 1
        
        if voters_batch:
            inserted, updated = self._insert_batch(voters_batch)
            stats['voters_added'] += inserted
            stats['voters_updated'] += updated
        
        stats['parts_created'] = len(self.part_cache)
        return stats
    
    def _parse_row(self, row) -> Optional[dict]:
        def get_str(key: str) -> Optional[str]:
            val = row.get(key, '')
            return str(val).strip() if val and str(val).strip() else None
        
        def get_int(key: str) -> Optional[int]:
            val = row.get(key, '')
            try:
                return int(float(val)) if val else None
            except:
                return None
        
        epic_no = get_str('EPIC_NO')
        if not epic_no:
            return None
        
        part_no = get_int('PART_NO')
        if not part_no:
            return None
        
        part_id = self._get_or_create_part(
            part_no,
            get_str('PART_NAME_EN'),
            get_str('PART_NAME_V1')
        )
        
        return {
            'epic_no': epic_no,
            'part_id': part_id,
            'slnoinpart': get_int('SLNOINPART'),
            'relation_type': get_str('RLN_TYPE'),
            'rln_fm_nm_en': get_str('RLN_FM_NM_EN'),
            'rln_l_nm_en': get_str('RLN_L_NM_EN'),
            'rln_fm_nm_v1': get_str('RLN_FM_NM_V1'),
            'rln_l_nm_v1': get_str('RLN_L_NM_V1'),
            'fm_name_en': get_str('FM_NAME_EN'),
            'lastname_en': get_str('LASTNAME_EN'),
            'fm_name_v1': get_str('FM_NAME_V1'),
            'lastname_v1': get_str('LASTNAME_V1'),
            'age': get_int('AGE'),
            'gender': get_str('GENDER'),
            'dob': get_str('DOB'),
            'mobile_no': get_str('MOBILE_NO'),
            'ac_no': get_int('AC_NO'),
            'section_no': get_int('SECTION_NO'),
            'pc_no': get_int('PC_NO'),
            'village_name_en': get_str('VILLAGE_NAME_EN'),
            'village_name_v1': get_str('VILLAGE_NAME_V1'),
            'tahsil_name_en': get_str('TAHSIL_NAME_EN'),
            'police_name_en': get_str('POLICEST_NAME_EN'),
            'postoff_pin': get_str('POSTOFF_PIN'),
            'c_house_no': get_str('C_HOUSE_NO'),
            'c_house_no_v1': get_str('C_HOUSE_NO_V1')
        }
    
    def _get_or_create_part(self, part_no: int, name_en: Optional[str], name_v1: Optional[str]) -> int:
        if part_no in self.part_cache:
            return self.part_cache[part_no]
        
        part = self.db.query(Part).filter(Part.part_no == part_no).first()
        
        if part:
            if not part.area_id:
                part.area_id = self.area_id
                self.db.flush()
            part_id = part.part_id
        else:
            part = Part(
                part_no=part_no,
                area_id=self.area_id,
                part_name_en=name_en,
                part_name_v1=name_v1
            )
            self.db.add(part)
            self.db.flush()
            part_id = part.part_id
        
        self.part_cache[part_no] = part_id
        return part_id
    
    def _insert_batch(self, voters: List[dict]) -> tuple:
        inserted = 0
        updated = 0
        
        for voter_data in voters:
            existing = self.db.query(Voter).filter(
                Voter.epic_no == voter_data['epic_no']
            ).first()
            
            if existing:
                for key, value in voter_data.items():
                    if key != 'epic_no' and value is not None:
                        setattr(existing, key, value)
                updated += 1
            else:
                voter = Voter(**voter_data)
                self.db.add(voter)
                inserted += 1
        
        self.db.flush()
        return inserted, updated


# ========================================
# USER ACCESS MANAGEMENT
# ========================================

@router.post("/assign-access", response_model=dict)
def assign_users_to_area(
    area_id: int = Form(...),
    user_emails: str = Form(..., description="Comma-separated emails"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Assign multiple users by email (comma-separated)"""
    
    area = db.query(Area).filter(Area.area_id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    
    if area.uploaded_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Only uploader can assign access")
    
    email_list = [email.strip().lower() for email in user_emails.split(',') if email.strip()]
    
    if not email_list:
        raise HTTPException(status_code=400, detail="No emails provided")
    
    users = db.query(User).filter(User.email.in_(email_list)).all()
    found_emails = {u.email.lower() for u in users}
    invalid_emails = set(email_list) - found_emails
    
    if invalid_emails:
        raise HTTPException(
            status_code=404,
            detail=f"Users not found: {', '.join(invalid_emails)}"
        )
    
    already_assigned = db.query(UserArea).filter(
        UserArea.area_id == area_id,
        UserArea.user_id.in_([u.user_id for u in users])
    ).all()
    already_assigned_ids = {ua.user_id for ua in already_assigned}
    
    newly_assigned_details = []
    for user in users:
        if user.user_id not in already_assigned_ids:
            user_area = UserArea(user_id=user.user_id, area_id=area_id)
            db.add(user_area)
            newly_assigned_details.append({
                "user_id": user.user_id,
                "email": user.email,
                "full_name": user.full_name
            })
    
    db.commit()
    
    return {
        "message": "Access assigned ✅",
        "area_id": area_id,
        "area_name": area.area_name,
        "newly_assigned": newly_assigned_details,
        "already_had_access": len(already_assigned_ids)
    }


@router.get("/search-users")
def search_users_for_assignment(
    query: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search users by name/email for dropdown"""
    
    search_pattern = f"%{query}%"
    
    users = db.query(User).filter(
        or_(
            User.email.ilike(search_pattern),
            User.full_name.ilike(search_pattern)
        ),
        User.is_active == True
    ).limit(limit).all()
    
    return {
        "query": query,
        "count": len(users),
        "users": [
            {
                "user_id": u.user_id,
                "email": u.email,
                "full_name": u.full_name or "N/A",
                "display_name": f"{u.full_name or 'N/A'} ({u.email})"
            }
            for u in users
        ]
    }


@router.get("/area-users/{area_id}")
def get_area_assigned_users(
    area_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all users with access to area"""
    
    area = db.query(Area).filter(Area.area_id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    
    user_area = db.query(UserArea).filter(
        UserArea.area_id == area_id,
        UserArea.user_id == current_user.user_id
    ).first()
    
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
                "is_uploader": u.user_id == area.uploaded_by
            }
            for u in users
        ]
    }


@router.delete("/revoke-access")
def revoke_user_access(
    area_id: int = Form(...),
    user_id: int = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke user access (cannot revoke uploader)"""
    
    area = db.query(Area).filter(Area.area_id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    
    if area.uploaded_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Only uploader can revoke")
    
    if user_id == area.uploaded_by:
        raise HTTPException(status_code=400, detail="Cannot revoke uploader access")
    
    user_area = db.query(UserArea).filter(
        UserArea.area_id == area_id,
        UserArea.user_id == user_id
    ).first()
    
    if not user_area:
        raise HTTPException(status_code=404, detail="User access not found")
    
    db.delete(user_area)
    db.commit()
    
    return {"message": "Access revoked"}


@router.get("/my-areas")
def get_my_accessible_areas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all areas accessible to current user"""
    
    user_areas = db.query(UserArea.area_id).filter(
        UserArea.user_id == current_user.user_id
    ).all()
    area_ids = [ua.area_id for ua in user_areas]
    
    if not area_ids:
        return {"total": 0, "page": page, "page_size": page_size, "areas": []}
    
    query = db.query(Area).filter(Area.area_id.in_(area_ids))
    total = query.count()
    
    offset = (page - 1) * page_size
    areas = query.order_by(Area.created_at.desc()).offset(offset).limit(page_size).all()
    
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
                "upload_date": a.upload_date
            }
            for a in areas
        ]
    }


# ========================================
# VALIDATION & TEMPLATE
# ========================================

@router.post("/validate")
async def validate_excel(file: UploadFile = File(...)):
    """Validate Excel before upload"""
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        original_columns = df.columns.tolist()
        df.columns = [col.upper() for col in df.columns]
        
        required = ['PART_NO', 'EPIC_NO']
        missing = [col for col in required if col not in df.columns]
        
        return {
            "valid": len(missing) == 0,
            "total_rows": len(df),
            "columns": original_columns,
            "missing": missing
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation failed: {str(e)}")


@router.get("/template")
def download_template():
    """Download Excel template"""
    
    sample = {
        'PART_NO': [1, 1, 2],
        'EPIC_NO': ['ABC1234567', 'XYZ9876543', 'DEF5555555'],
        'FM_NAME_EN': ['John', 'Jane', 'Mike'],
        'LASTNAME_EN': ['Doe', 'Smith', 'Johnson'],
        'AGE': [35, 28, 42],
        'GENDER': ['Male', 'Female', 'Male']
    }
    
    df = pd.DataFrame(sample)
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Voters')
    
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=voter_template.xlsx'}
    )
