from typing import Generator, Union
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.volunteer import Volunteer
from app.core.security import decode_access_token


security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Union[User, Volunteer]:
    """
    Get current authenticated user (Politician or Volunteer).
    Checks the 'type' field in JWT token to determine which table to query.
    """
    payload = decode_access_token(credentials.credentials)
    email: str = payload.get("sub")
    user_type: str = payload.get("type", "user")  # Default to 'user' for backward compatibility
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    # ✅ Check user type and query the appropriate table
    if user_type == "volunteer":
        # Query Volunteer table
        volunteer = db.query(Volunteer).filter(Volunteer.email == email).first()
        
        if not volunteer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Volunteer not found"
            )
        
        if not volunteer.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Volunteer account is inactive"
            )
        
        # ✅ Also check if parent politician is active
        if not volunteer.politician.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Parent user account is not active"
            )
        
        return volunteer
    
    else:
        # Query User table (Politician)
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive"
            )
        
        return user


def get_current_active_user(
    current_user: Union[User, Volunteer] = Depends(get_current_user)
) -> Union[User, Volunteer]:
    """
    Verify user is active (works for both User and Volunteer).
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# ✅ NEW: Helper function to get effective user ID for filtering
def get_effective_user_id(current_user: Union[User, Volunteer]) -> int:
    """
    Returns the user_id to use for filtering UserArea data.
    
    - If User (Politician): returns their own user_id
    - If Volunteer: returns their politician_id (parent user's ID)
    
    This allows volunteers to see data from their parent politician's assigned areas.
    """
    # Check if it's a Volunteer (has politician_id attribute)
    if hasattr(current_user, 'politician_id'):
        # This is a Volunteer - return parent politician's ID
        return current_user.politician_id
    else:
        # This is a User (Politician) - return their own ID
        return current_user.user_id
