from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, Text, Index, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Voter(Base):
    __tablename__ = "voters"

    voter_id = Column(BigInteger, primary_key=True, index=True)
    epic_no = Column(String(50), unique=True, index=True, nullable=False)
    part_id = Column(Integer, ForeignKey("parts.part_id", ondelete="RESTRICT"), nullable=False)

    # ==============================
    # Polling Voter Information (Telugu / base)
    # ==============================
    ward_no = Column(String(10), index=True)

    # Telugu text
    district = Column(String(100))
    municipality = Column(String(200), index=True, nullable=False)
    polling_station_no = Column(String(10), index=True, nullable=False)
    polling_station_location = Column(Text)
    voter_name = Column(String(200), index=True)
    relation_name = Column(String(200))

    # English text
    district_en = Column(String(100))
    municipality_en = Column(String(200), index=True)
    polling_station_location_en = Column(Text)
    voter_name_en = Column(String(200), index=True)
    relation_name_en = Column(String(200))

    serial_no = Column(String(10))
    age = Column(Integer)
    gender = Column(String(20))
    house_no = Column(String(100))
    date_time = Column(String(100))  # custom text format
    pdf_url = Column(Text, nullable=True)
    phone_number = Column(String(15), nullable=True, index=True)

    # ==============================
    # ✅ NEW: Survey Tracking
    # ==============================
    form_id = Column(Integer, ForeignKey("form_data.id", ondelete="SET NULL"), nullable=True, index=True)
    is_surveyed = Column(Boolean, default=False, nullable=False, index=True)
    survey_date = Column(DateTime(timezone=True), nullable=True)

    # ==============================
    # Metadata
    # ==============================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ==============================
    # Relationships
    # ==============================
    part = relationship("Part", back_populates="voters")
    form = relationship("FormData", foreign_keys=[form_id], back_populates="surveyed_voters")

    __table_args__ = (
        Index('idx_voters_epic_no', 'epic_no'),
        Index('idx_voters_voter_name', 'voter_name'),
        Index('idx_voters_voter_name_en', 'voter_name_en'),
        Index('idx_voters_municipality', 'municipality'),
        Index('idx_voters_municipality_en', 'municipality_en'),
        Index('idx_voters_polling_station', 'polling_station_no'),
        Index('idx_voters_ward_no', 'ward_no'),
        Index('idx_voters_house_no', 'house_no'),
        Index('idx_voters_phone_number', 'phone_number'),
        Index('idx_voters_part_id', 'part_id'),
        Index('idx_voters_form_id', 'form_id'),  # ✅ NEW
        Index('idx_voters_is_surveyed', 'is_surveyed'),  # ✅ NEW
    )

    def __repr__(self):
        return f"<Voter {self.epic_no} - {self.voter_name}>"
