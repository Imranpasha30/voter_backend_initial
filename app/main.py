from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.V1.router import api_router
from app.db.session import SessionLocal
from app.db.base import Base
from app.db.session import engine

def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG
    )
    
    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_CREDENTIALS,
        allow_methods=settings.CORS_METHODS,
        allow_headers=settings.CORS_HEADERS,
    )
    
    # Include routers
    application.include_router(api_router, prefix="/api")
    
    @application.get("/")
    def root():
        return {"message": "Voter Management API", "status": "running"}
    
    @application.get("/health")
    def health_check():
        return {"status": "healthy"}
    
    return application

app = create_application()

@app.on_event("startup")
def on_startup():
    """Create tables on startup"""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
