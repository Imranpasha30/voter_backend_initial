from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.volunteer import Volunteer
from app.schemas.volunteer import VolunteerLogin, VolunteerResponse
from app.core.security import create_access_token, verify_password, get_current_volunteer

router = APIRouter()


@router.post("/login", response_model=dict)
def volunteer_login(
    credentials: VolunteerLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """Login volunteer with SHA256 password verification"""

    print(f"\n{'='*60}")
    print(f"🔍 VOLUNTEER LOGIN ATTEMPT")
    print(f"{'='*60}")
    print(f"📧 Email: {credentials.email}")

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

    print(f"✅ Volunteer FOUND: {volunteer.username}")

    # Support both plain text and SHA256 hashed passwords
    is_hashed = len(volunteer.password) == 64
    if is_hashed:
        print(f"🔒 SHA256 hashed password")
        password_valid = verify_password(credentials.password, volunteer.password)
    else:
        print(f"🔓 Plain text password")
        password_valid = credentials.password == volunteer.password

    if not password_valid:
        print(f"❌ PASSWORD MISMATCH")
        print(f"{'='*60}\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not volunteer.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Volunteer account is inactive"
        )

    if not volunteer.politician.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Main user account is not active"
        )

    print(f"🎉 LOGIN SUCCESSFUL!")
    print(f"{'='*60}\n")

    # ✅ Token payload — type="volunteer", id=volunteer.id, sub=email
    access_token = create_access_token(
        data={
            "sub": volunteer.email,
            "type": "volunteer",
            "id": volunteer.id          # ✅ used by get_current_volunteer & get_politician_id_from_token
        }
    )

    volunteer_data = {
        "id": volunteer.id,
        "politician_id": volunteer.politician_id,
        "username": volunteer.username,
        "email": volunteer.email,
        "phone_number": volunteer.phone_number,
        "is_active": volunteer.is_active,
        "created_at": volunteer.created_at,
        "politician_name": volunteer.politician.full_name,
        "politician_profile_image_url": volunteer.politician.profile_image_url,
    }

    print(f"📦 Politician: {volunteer.politician.full_name}")
    print(f"📦 Politician Image: {volunteer.politician.profile_image_url}")

    return {
        "volunteer": volunteer_data,
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=VolunteerResponse)
def get_current_volunteer_info(
    current_volunteer: Volunteer = Depends(get_current_volunteer),
    db: Session = Depends(get_db)
):
    """Get current volunteer information with politician details"""

    volunteer = db.query(Volunteer).options(
        joinedload(Volunteer.politician)
    ).filter(Volunteer.id == current_volunteer.id).first()

    if not volunteer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volunteer not found"
        )

    return {
        "id": volunteer.id,
        "politician_id": volunteer.politician_id,
        "username": volunteer.username,
        "email": volunteer.email,
        "phone_number": volunteer.phone_number,
        "is_active": volunteer.is_active,
        "created_at": volunteer.created_at,
        "politician_name": volunteer.politician.full_name,
        "politician_profile_image_url": volunteer.politician.profile_image_url,
    }


