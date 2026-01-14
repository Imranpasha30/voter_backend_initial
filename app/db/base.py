from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()



__all__ = ["Base", "User", "LoginLog", "Part", "Voter", "UserArea", "Volunteer", "FormData", "VolunteerLocation"]
