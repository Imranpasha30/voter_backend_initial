from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from app.db.session import get_db
from app.models.volunteer import Volunteer
from app.schemas.volunteer import VolunteerLogin, VolunteerResponse
from app.core.security import create_access_token, verify_password

router = APIRouter()
@router.post("/login", response_model=dict)
def volunteer_login(
    credentials: VolunteerLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """Login volunteer with SHA256 password verification"""
    
    # Debug logging
    print(f"\n{'='*60}")
    print(f"🔍 VOLUNTEER LOGIN ATTEMPT")
    print(f"{'='*60}")
    print(f"📧 Email: {credentials.email}")
    print(f"🔑 Password received: '{credentials.password}'")
    
    # Fetch volunteer with politician relationship
    volunteer = db.query(Volunteer).options(
        joinedload(Volunteer.politician)
    ).filter(Volunteer.email == credentials.email).first()
    
    if not volunteer:
        print(f"❌ Volunteer NOT FOUND in database")
        print(f"{'='*60}\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    print(f"✅ Volunteer FOUND in database")
    print(f"👤 Username: {volunteer.username}")
    print(f"🔐 Password in DB: '{volunteer.password}'")
    print(f"📏 Password length: {len(volunteer.password)}")
    print(f"🔢 Is it a hash? (64 chars): {len(volunteer.password) == 64}")
    
    # Check if password is hashed or plain
    is_hashed = len(volunteer.password) == 64
    
    if is_hashed:
        print(f"🔒 Password appears to be SHA256 hashed")
        # Verify using SHA256
        password_valid = verify_password(credentials.password, volunteer.password)
        print(f"✔️ SHA256 verification result: {password_valid}")
    else:
        print(f"🔓 Password appears to be plain text")
        # Direct comparison
        password_valid = credentials.password == volunteer.password
        print(f"✔️ Plain text comparison result: {password_valid}")
    
    if not password_valid:
        print(f"❌ PASSWORD MISMATCH!")
        print(f"{'='*60}\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if volunteer account is active
    if not volunteer.is_active:
        print(f"⚠️ Volunteer is INACTIVE")
        print(f"{'='*60}\n")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Volunteer account is inactive"
        )
    
    # Check if parent user (politician) is active
    if not volunteer.politician.is_active:
        print(f"⚠️ Parent user (Politician) is INACTIVE")
        print(f"👤 Politician ID: {volunteer.politician.user_id}")
        print(f"📧 Politician Email: {volunteer.politician.email}")
        print(f"{'='*60}\n")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Main user account is not active"
        )
    
    print(f"🎉 LOGIN SUCCESSFUL!")
    print(f"✅ Volunteer is active")
    print(f"✅ Parent user (Politician) is active")
    print(f"{'='*60}\n")
    
    # Create access token with volunteer type
    access_token = create_access_token(
        data={"sub": volunteer.email, "type": "volunteer", "id": volunteer.id}
    )
    
    return {
        "volunteer": VolunteerResponse.from_orm(volunteer),
        "access_token": access_token,
        "token_type": "bearer"
    }
