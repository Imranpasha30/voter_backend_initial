from fastapi import APIRouter
from app.api.V1.endpoints import auth, voters, parts, areas, volunteers, volunteer_auth, excel_upload, location, logs, documents   # ✅ Add documents


api_router = APIRouter()


api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(volunteer_auth.router, prefix="/volunteer-auth", tags=["Volunteer Auth"])
api_router.include_router(excel_upload.router, prefix="/upload", tags=["Upload"])
api_router.include_router(location.router, prefix="/location", tags=["Location Tracking"])
api_router.include_router(areas.router, prefix="/areas", tags=["Areas"])
api_router.include_router(volunteers.router, prefix="/volunteers", tags=["Volunteers"])
api_router.include_router(parts.router, prefix="/parts", tags=["Parts"])
api_router.include_router(voters.router, prefix="/voters", tags=["Voters"])
api_router.include_router(logs.router, prefix="/logs", tags=["Logs"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])  # ✅ ADD THIS LINE
