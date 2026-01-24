from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class VoterChangeLog(Base):
    __tablename__ = "voter_change_logs"
    
    log_id = Column(Integer, primary_key=True, index=True)
    
    # Voter Information
    voter_id = Column(Integer, ForeignKey("voters.voter_id", ondelete="CASCADE"), nullable=False)
    epic_no = Column(String(20), nullable=False, index=True)
    
    # User Information (who made the change)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    volunteer_id = Column(Integer, ForeignKey("volunteers.id", ondelete="SET NULL"), nullable=True)
    user_type = Column(String(20), nullable=False)  # 'politician' or 'volunteer'
    user_name = Column(String(255), nullable=False)
    user_email = Column(String(255), nullable=False)
    
    # Change Details
    action_type = Column(String(20), nullable=False)  # 'UPDATE', 'CREATE', 'DELETE'
    field_changed = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    
    # Metadata
    change_timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ip_address = Column(String(50), nullable=True)
    device_info = Column(String(255), nullable=True)
    
    # Relationships
    voter = relationship("Voter", backref="change_logs")
    user = relationship("User", backref="change_logs")
    volunteer = relationship("Volunteer", backref="change_logs")
    
    __table_args__ = (
        Index('idx_voter_change_logs_voter_id', 'voter_id'),
        Index('idx_voter_change_logs_epic_no', 'epic_no'),
        Index('idx_voter_change_logs_user_id', 'user_id'),
        Index('idx_voter_change_logs_volunteer_id', 'volunteer_id'),
        Index('idx_voter_change_logs_timestamp', 'change_timestamp'),
    )
