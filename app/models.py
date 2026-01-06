from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))


# ✅ New LoginLog table
# ✅ Updated LoginLog table
class LoginLog(Base):
    __tablename__ = "login_logs"
    
    log_id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    phone_number = Column(String(15), nullable=False, index=True)
    login_time = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    
    user = relationship("User")



class Part(Base):
    __tablename__ = "parts"
    
    part_id = Column(Integer, primary_key=True, index=True)
    part_no = Column(Integer, unique=True, nullable=False, index=True)
    part_name_en = Column(String(255))
    part_name_v1 = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    voters = relationship("Voter", back_populates="part")


class Voter(Base):
    __tablename__ = "voters"
    
    voter_id = Column(BigInteger, primary_key=True, index=True)
    epic_no = Column(String(50), unique=True, nullable=False, index=True)
    part_id = Column(Integer, ForeignKey("parts.part_id"), nullable=False)
    
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
    
    part = relationship("Part", back_populates="voters")
