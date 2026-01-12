from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
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

# Constants (like Rust)
CHUNK_SIZE = 1000


# ========================================
# EXCEL UPLOAD WITH RUST-STYLE PERFORMANCE
# ========================================

@router.post("/upload", response_model=dict)
async def upload_excel(
    area_name: str = Form(..., description="Geographic area name"),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload Excel file with voter data (Rust-inspired performance)
    
    **Excel columns (case-insensitive):**
    - PART_NO, EPIC_NO (required)
    - All other voter fields (optional)
    """
    
    # Validate file
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Use .xlsx or .xls")
    
    try:
        # Read Excel
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Normalize column names to lowercase
        df.columns = [col.upper() for col in df.columns]
        
        print(f"📊 Excel loaded: {len(df)} rows, {len(df.columns)} columns")
        print(f"📋 Columns: {df.columns.tolist()}")
        
        # Validate required columns
        required = ['PART_NO', 'EPIC_NO']
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing)}"
            )
        
        # Clean data
        df = df.fillna('')
        
        # Create Area
        area = Area(
            area_name=area_name,
            description=description,
            uploaded_by=current_user.user_id,
            file_name=file.filename,
            total_voters=0
        )
        db.add(area)
        db.flush()
        
        print(f"✅ Area created: {area.area_id} - {area_name}")
        
        # Auto-assign to user
        user_area = UserArea(
            user_id=current_user.user_id,
            area_id=area.area_id
        )
        db.add(user_area)
        db.flush()
        
        # Process with Rust-style batching
        importer = VoterImporter(db, area.area_id)
        stats = await importer.process_dataframe(df)
        
        # Update total voters
        area.total_voters = stats['voters_added'] + stats['voters_updated']
        
        db.commit()
        
        print(f"✅ Upload completed!")
        print(f"   Parts: {stats['parts_created']}")
        print(f"   Voters added: {stats['voters_added']}")
        print(f"   Voters updated: {stats['voters_updated']}")
        
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
        print(f"❌ Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ========================================
# VOTER IMPORTER (Rust-inspired)
# ========================================

class VoterImporter:
    def __init__(self, db: Session, area_id: int):
        self.db = db
        self.area_id = area_id
        self.part_cache: Dict[int, int] = {}
        self.processed_epics = set()
    
    async def process_dataframe(self, df: pd.DataFrame) -> dict:
        """Process DataFrame with batching like Rust implementation"""
        
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
                # Parse row
                voter_data = self._parse_row(row)
                
                if not voter_data:
                    stats['errors_count'] += 1
                    continue
                
                # Skip duplicates
                if voter_data['epic_no'] in self.processed_epics:
                    continue
                
                self.processed_epics.add(voter_data['epic_no'])
                voters_batch.append(voter_data)
                
                # Batch insert (like Rust CHUNK_SIZE)
                if len(voters_batch) >= CHUNK_SIZE:
                    inserted, updated = self._insert_batch(voters_batch)
                    stats['voters_added'] += inserted
                    stats['voters_updated'] += updated
                    voters_batch.clear()
                    print(f"💾 Batch committed: {stats['voters_added'] + stats['voters_updated']} processed")
            
            except Exception as e:
                stats['errors'].append(f"Row {idx + 2}: {str(e)}")
                stats['errors_count'] += 1
        
        # Final batch
        if voters_batch:
            inserted, updated = self._insert_batch(voters_batch)
            stats['voters_added'] += inserted
            stats['voters_updated'] += updated
        
        stats['parts_created'] = len(self.part_cache)
        
        return stats
    
    def _parse_row(self, row) -> Optional[dict]:
        """Parse Excel row to voter dict"""
        
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
        
        # Get or create part
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
        """Get or create part with caching"""
        
        # Check cache
        if part_no in self.part_cache:
            return self.part_cache[part_no]
        
        # Check database
        part = self.db.query(Part).filter(Part.part_no == part_no).first()
        
        if part:
            # Update with area_id if not set
            if not part.area_id:
                part.area_id = self.area_id
                self.db.flush()
            part_id = part.part_id
        else:
            # Create new part
            part = Part(
                part_no=part_no,
                area_id=self.area_id,
                part_name_en=name_en,
                part_name_v1=name_v1
            )
            self.db.add(part)
            self.db.flush()
            part_id = part.part_id
            print(f"✅ Part created: {part_no} (ID: {part_id})")
        
        self.part_cache[part_no] = part_id
        return part_id
    
    def _insert_batch(self, voters: List[dict]) -> tuple:
        """Batch insert with ON CONFLICT handling"""
        
        inserted = 0
        updated = 0
        
        for voter_data in voters:
            # Check if exists
            existing = self.db.query(Voter).filter(
                Voter.epic_no == voter_data['epic_no']
            ).first()
            
            if existing:
                # Update
                for key, value in voter_data.items():
                    if key != 'epic_no' and value is not None:
                        setattr(existing, key, value)
                updated += 1
            else:
                # Insert
                voter = Voter(**voter_data)
                self.db.add(voter)
                inserted += 1
        
        self.db.flush()
        return inserted, updated


# ========================================
# VALIDATION ENDPOINT
# ========================================

@router.post("/validate")
async def validate_excel(file: UploadFile = File(...)):
    """Validate Excel structure before upload"""
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Normalize columns
        original_columns = df.columns.tolist()
        df.columns = [col.upper() for col in df.columns]
        
        required = ['PART_NO', 'EPIC_NO']
        missing = [col for col in required if col not in df.columns]
        
        sample = df.head(5).to_dict('records')
        
        return {
            "valid": len(missing) == 0,
            "total_rows": len(df),
            "original_columns": original_columns,
            "normalized_columns": df.columns.tolist(),
            "missing_required": missing,
            "sample_data": sample
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation failed: {str(e)}")


# ========================================
# DOWNLOAD TEMPLATE
# ========================================

@router.get("/template")
def download_template():
    """Download sample Excel template"""
    
    sample = {
        'PART_NO': [1, 1, 2],
        'EPIC_NO': ['ABC1234567', 'XYZ9876543', 'DEF5555555'],
        'SLNOINPART': [1, 2, 1],
        'FM_NAME_EN': ['John', 'Jane', 'Mike'],
        'LASTNAME_EN': ['Doe', 'Smith', 'Johnson'],
        'AGE': [35, 28, 42],
        'GENDER': ['Male', 'Female', 'Male'],
        'MOBILE_NO': ['9876543210', '9123456789', '9988776655'],
        'AC_NO': [43, 43, 43],
        'VILLAGE_NAME_EN': ['Hyderabad', 'Hyderabad', 'Secunderabad']
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
