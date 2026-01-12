from sqlalchemy.orm import Session
from app.db.base import Base
from app.db.session import engine
from app.core.security import get_password_hash
from app.models.user import User


def init_db(db: Session) -> None:
    """Initialize database with default data"""
    Base.metadata.create_all(bind=engine)
    
    # Create default admin user if not exists
    admin = db.query(User).filter(User.email == "admin@example.com").first()
    if not admin:
        admin = User(
            email="admin@example.com",
            password_hash=get_password_hash("admin123"),
            full_name="System Admin",
            is_active=True
        )
        db.add(admin)
        db.commit()
