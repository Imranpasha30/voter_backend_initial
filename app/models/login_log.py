from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class LoginLog(Base):
    __tablename__ = "login_logs"
    
    log_id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="NO ACTION"), nullable=False)
    phone_number = Column(String(15), nullable=False, index=True)
    login_time = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    
    # Relationships
    user = relationship("User", back_populates="login_logs")
