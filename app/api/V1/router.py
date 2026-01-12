from fastapi import APIRouter
from app.api.V1.endpoints import auth, voters, parts, areas, volunteers, volunteer_auth

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(volunteer_auth.router, prefix="/volunteer-auth", tags=["Volunteer Auth"])  # ✅ NEW
api_router.include_router(areas.router, prefix="/areas", tags=["Areas"])
api_router.include_router(volunteers.router, prefix="/volunteers", tags=["Volunteers"])
api_router.include_router(parts.router, prefix="/parts", tags=["Parts"])
api_router.include_router(voters.router, prefix="/voters", tags=["Voters"])
