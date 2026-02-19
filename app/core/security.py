"""
Security utilities for password hashing and JWT tokens
Uses SHA256 for password hashing (simple, no dependencies issues)
"""

from datetime import datetime, timedelta
from typing import Optional
import hashlib
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

# ✅ HTTPBearer for JWT authentication
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using SHA256"""
    hashed = hashlib.sha256(plain_password.encode()).hexdigest()
    return hashed == hashed_password


def get_password_hash(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_volunteer(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get current volunteer from JWT token"""
    from app.models.volunteer import Volunteer

    try:
        token = credentials.credentials
        payload = decode_access_token(token)

        volunteer_id = payload.get("id")
        volunteer_type = payload.get("type")

        if volunteer_type != "volunteer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized as volunteer"
            )
        if volunteer_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )

        volunteer = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
        if not volunteer:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Volunteer not found")
        if not volunteer.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Volunteer account is inactive")

        return volunteer

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication error: {str(e)}")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get current user (politician) from JWT token"""
    from app.models.user import User

    try:
        token = credentials.credentials
        payload = decode_access_token(token)

        user_email = payload.get("sub")
        user_type = payload.get("type")

        if user_type == "volunteer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized as politician"
            )
        if user_email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )

        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive")

        return user

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication error: {str(e)}")


# ✅ NEW: Universal dep — works for BOTH politician and volunteer tokens
# Use this on any endpoint that both roles can call (e.g. voter list)
def get_politician_id_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> int:
    """
    Universal dependency — resolves to politician's user_id from ANY token type.
    - Politician token (type='user'):      sub=email  → queries User  → returns user.user_id
    - Volunteer token  (type='volunteer'): id=vol_id  → queries Volunteer → returns volunteer.politician_id
    """
    from app.models.user import User
    from app.models.volunteer import Volunteer

    try:
        token = credentials.credentials
        payload = decode_access_token(token)

        token_type = payload.get("type")

        # ─── Politician token ───
        if token_type != "volunteer":
            user_email = payload.get("sub")
            if not user_email:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

            user = db.query(User).filter(User.email == user_email).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive")

            return user.user_id  # ✅ politician calling directly

        # ─── Volunteer token ───
        volunteer_id = payload.get("id")
        if not volunteer_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid volunteer token payload")

        volunteer = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
        if not volunteer:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Volunteer not found")
        if not volunteer.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Volunteer account is inactive")

        return volunteer.politician_id  # ✅ volunteer → their politician's id

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication error: {str(e)}")
