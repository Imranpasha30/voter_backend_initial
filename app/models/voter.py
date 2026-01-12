from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Voter(Base):
    __tablename__ = "voters"
    
    voter_id = Column(BigInteger, primary_key=True, index=True)
    epic_no = Column(String(50), unique=True, nullable=False, index=True)
    part_id = Column(Integer, ForeignKey("parts.part_id", ondelete="RESTRICT"), nullable=False)
    
    slnoinpart = Column(Integer)
    relation_type = Column(String(10))
    rln_fm_nm_en = Column(String(100))
    rln_l_nm_en = Column(String(100))
    rln_fm_nm_v1 = Column(String(100))
    rln_l_nm_v1 = Column(String(100))
    fm_name_en = Column(String(100), index=True)
    lastname_en = Column(String(100), index=True)
    fm_name_v1 = Column(String(100))
    lastname_v1 = Column(String(100))
    age = Column(Integer)
    gender = Column(String(10))
    dob = Column(String(20))
    mobile_no = Column(String(15), index=True)
    
    ac_no = Column(Integer, index=True)
    section_no = Column(Integer)
    pc_no = Column(Integer, index=True)
    
    village_name_en = Column(String(100), index=True)
    village_name_v1 = Column(String(100))
    tahsil_name_en = Column(String(100), index=True)
    police_name_en = Column(String(100))
    postoff_pin = Column(String(10))
    c_house_no = Column(String(50))
    c_house_no_v1 = Column(String(50))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    part = relationship("Part", back_populates="voters")
