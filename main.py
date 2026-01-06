from fastapi import FastAPI, Depends, HTTPException, Request, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional
from datetime import datetime

from app.database import get_db, engine
from app.models import Base, LoginLog, User, Voter, Part
from app.schemas import (
    UserCreate, UserLogin, UserResponse, LoginResponse,
    VoterCreate, VoterUpdate, VoterResponse, VotersListResponse,
    PartResponse, PartsListResponse
)
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Voter Management API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== AUTH ROUTES ====================

@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_user = User(
        email=user.email,
        password_hash=get_password_hash(user.password),
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/api/auth/login", response_model=LoginResponse)
def login(credentials: UserLogin, request: Request, db: Session = Depends(get_db)):
    """Login user with phone number tracking"""
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # ✅ Create login log entry (only phone number)
    login_log = LoginLog(
        user_id=user.user_id,
        phone_number=credentials.phone_number,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:255]
    )
    db.add(login_log)
    db.commit()
    
    access_token = create_access_token(data={"sub": user.email})
    
    return LoginResponse(
        user=user,
        access_token=access_token,
        token_type="bearer"
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return current_user

# ==================== PARTS ROUTES (Constituencies) ====================

@app.get("/api/constituencies", response_model=PartsListResponse)
@app.get("/api/assembly-constituencies", response_model=PartsListResponse)
def get_parts(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all parts (constituencies) with voter counts"""
    query = db.query(
        Part,
        func.count(Voter.voter_id).label('voter_count')
    ).outerjoin(Voter, Part.part_id == Voter.part_id).group_by(Part.part_id)
    
    # Search
    if search:
        query = query.filter(
            or_(
                Part.part_name_en.ilike(f"%{search}%"),
                Part.part_name_v1.ilike(f"%{search}%")
            )
        )
    
    # Order by part_no
    query = query.order_by(Part.part_no)
    
    # Get total count
    total = query.count()
    
    # Pagination
    offset = (page - 1) * page_size
    results = query.offset(offset).limit(page_size).all()
    
    # Map to response
    parts = []
    for part, voter_count in results:
        part_dict = {
            "part_id": part.part_id,
            "part_no": part.part_no,
            "part_name_en": part.part_name_en,
            "part_name_v1": part.part_name_v1,
            "created_at": part.created_at,
            "voter_count": voter_count
        }
        parts.append(PartResponse(**part_dict))
    
    return PartsListResponse(
        total=total,
        page=page,
        page_size=page_size,
        parts=parts
    )

@app.get("/api/parts/{part_id}", response_model=PartResponse)
def get_part(
    part_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific part by ID"""
    part = db.query(Part).filter(Part.part_id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    
    voter_count = db.query(func.count(Voter.voter_id)).filter(Voter.part_id == part_id).scalar()
    
    return PartResponse(
        part_id=part.part_id,
        part_no=part.part_no,
        part_name_en=part.part_name_en,
        part_name_v1=part.part_name_v1,
        created_at=part.created_at,
        voter_count=voter_count
    )

# ==================== VOTER ROUTES ====================

@app.get("/api/voters", response_model=VotersListResponse)
def get_voters_by_ac(
    ac_no: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voters by part number (ac_no in Flutter is part_no)"""
    # Get part_id from part_no (Flutter sends as ac_no)
    part = db.query(Part).filter(Part.part_no == ac_no).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    
    query = db.query(Voter).filter(Voter.part_id == part.part_id)
    
    if search:
        query = query.filter(
            or_(
                Voter.fm_name_en.ilike(f"%{search}%"),
                Voter.lastname_en.ilike(f"%{search}%"),
                Voter.epic_no.ilike(f"%{search}%")
            )
        )
    
    query = query.order_by(Voter.slnoinpart)
    
    total = query.count()
    offset = (page - 1) * page_size
    voters = query.offset(offset).limit(page_size).all()
    
    return VotersListResponse(
        total=total,
        page=page,
        page_size=page_size,
        voters=voters
    )

@app.get("/api/voters/{epic_no}", response_model=VoterResponse)
def get_voter_by_epic(
    epic_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get voter by EPIC number"""
    voter = db.query(Voter).filter(Voter.epic_no == epic_no).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    
    # Get part name
    part = db.query(Part).filter(Part.part_id == voter.part_id).first()
    voter_dict = voter.__dict__.copy()
    voter_dict['part_no'] = part.part_no if part else None
    voter_dict['part_name'] = part.part_name_en if part else None
    
    return VoterResponse(**voter_dict)

@app.get("/api/voters/search", response_model=VotersListResponse)
def search_voters(
    query: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search voters by name or EPIC"""
    voter_query = db.query(Voter).filter(
        or_(
            Voter.fm_name_en.ilike(f"%{query}%"),
            Voter.lastname_en.ilike(f"%{query}%"),
            Voter.epic_no.ilike(f"%{query}%")
        )
    )
    
    total = voter_query.count()
    offset = (page - 1) * page_size
    voters = voter_query.offset(offset).limit(page_size).all()
    
    return VotersListResponse(
        total=total,
        page=page,
        page_size=page_size,
        voters=voters
    )

@app.post("/api/voters/create", response_model=VoterResponse, status_code=status.HTTP_201_CREATED)
def create_voter(
    voter: VoterCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new voter"""
    # Check if EPIC already exists
    existing = db.query(Voter).filter(Voter.epic_no == voter.epic_no).first()
    if existing:
        raise HTTPException(status_code=400, detail="EPIC number already exists")
    
    # Verify part exists
    part = db.query(Part).filter(Part.part_id == voter.part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    
    db_voter = Voter(**voter.dict())
    db.add(db_voter)
    db.commit()
    db.refresh(db_voter)
    
    return db_voter

@app.put("/api/voters/{voter_id}", response_model=VoterResponse)
def update_voter(
    voter_id: int,
    voter_update: VoterUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update voter details"""
    voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    # Update only provided fields
    for key, value in voter_update.dict(exclude_unset=True).items():
        setattr(voter, key, value)
    
    db.commit()
    db.refresh(voter)
    
    return voter

@app.delete("/api/voters/{voter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voter(
    voter_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete voter"""
    voter = db.query(Voter).filter(Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    
    db.delete(voter)
    db.commit()
    
    return None

# ==================== HEALTH CHECK ====================

@app.get("/")
def root():
    return {"message": "Voter Management API", "status": "running", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
