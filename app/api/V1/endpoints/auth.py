from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.models.user import User
from app.models.login_log import LoginLog
from app.schemas.user import UserCreate, UserLogin, UserResponse, LoginResponse
from app.core.security import get_password_hash, verify_password, create_access_token
from app.api.deps import get_current_user


router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
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


@router.post("/login", response_model=LoginResponse)
def login(credentials: UserLogin, request: Request, db: Session = Depends(get_db)):
    
    print(f"\n{'='*50}")
    print(f"📧 Email received: '{credentials.email}'")
    print(f"🔑 Password received: '{credentials.password}'")
    
    user = db.query(User).filter(User.email == credentials.email).first()
    print(f"👤 User found: {user is not None}")
    
    if not user:
        print("❌ FAIL: User not found in DB")
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    print(f"🔐 Hash in DB: '{user.password_hash}'")
    print(f"📏 Hash length: {len(user.password_hash)}")
    
    # Manually compute what hash SHOULD be
    import hashlib
    expected_hash = hashlib.sha256(credentials.password.encode()).hexdigest()
    print(f"🧮 Expected hash: '{expected_hash}'")
    print(f"✅ Match: {expected_hash == user.password_hash}")
    
    if not verify_password(credentials.password, user.password_hash):
        print("❌ FAIL: Password mismatch")
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    if not user.is_active:
        print("❌ FAIL: User inactive")
        raise HTTPException(status_code=400, detail="User is inactive")

    user.last_login = datetime.utcnow()

    login_log = LoginLog(
        user_id=user.user_id,
        phone_number=credentials.phone_number,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:255]
    )
    db.add(login_log)
    db.commit()

    access_token = create_access_token(
        data={"sub": user.email, "type": "user"}  # ✅ add type
    )

    print(f"🎉 Login SUCCESS for {user.email}")
    print(f"{'='*50}\n")

    return LoginResponse(user=user, access_token=access_token)

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return current_user
