from sqlalchemy import Column, Integer, String, DateTime, Text, Index, Boolean, CheckConstraint
from sqlalchemy.sql import func
from app.db.base import Base


class PollingVoter(Base):
    __tablename__ = "polling_voters"

    id = Column(Integer, primary_key=True, index=True)
    voter_id = Column(String(50), unique=True, index=True, nullable=False)  # EPIC_No
    ward_no = Column(String(10), index=True)
    district = Column(String(100))
    municipality = Column(String(200), index=True, nullable=False)
    polling_station_no = Column(String(10), index=True, nullable=False)
    polling_station_location = Column(Text)
    serial_no = Column(String(10))
    voter_name = Column(String(200), index=True)
    relation_name = Column(String(200))
    age = Column(Integer)
    gender = Column(String(20))
    house_no = Column(String(100))
    date_time = Column(String(100))  # Store as string since format is custom
    pdf_url = Column(Text, nullable=True)
    
    # ✅ NEW: Voter tracking fields
    phone_number = Column(String(15), nullable=True, index=True)
    is_voted = Column(Boolean, nullable=False, default=False, server_default='false', index=True)
    voting_status = Column(String(10), nullable=True, index=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_polling_voters_municipality', 'municipality'),
        Index('idx_polling_voters_polling_station', 'polling_station_no'),
        Index('idx_polling_voters_voter_id', 'voter_id'),
        Index('idx_polling_voters_voter_name', 'voter_name'),
        Index('idx_polling_voters_house_no', 'house_no'),
        Index('idx_polling_voters_phone_number', 'phone_number'),
        Index('idx_polling_voters_is_voted', 'is_voted'),
        Index('idx_polling_voters_voting_status', 'voting_status'),
        # ✅ Check constraint for voting_status
        CheckConstraint(
            "voting_status IS NULL OR voting_status IN ('red', 'yellow', 'green')",
            name='check_voting_status'
        ),
    )

    def __repr__(self):
        return f"<PollingVoter {self.voter_id} - {self.voter_name}>"
