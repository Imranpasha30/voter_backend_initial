from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import models AFTER Base
# from app.models.user import User
# from app.models.login_log import LoginLog
# from app.models.part import Part
# from app.models.voter import Voter

__all__ = ["Base", "User", "LoginLog", "Part", "Voter"]
