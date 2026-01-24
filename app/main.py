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
    """Create tables on startup and verify configuration"""
    Base.metadata.create_all(bind=engine)
    
    # ✅ DEBUG: Verify settings are loaded correctly
    print("")
    print("=" * 80)
    print("🚀 FASTAPI APPLICATION STARTUP")
    print("=" * 80)
    print(f"📦 App Name: {settings.APP_NAME}")
    print(f"📝 Version: {settings.APP_VERSION}")
    print(f"🔧 Debug Mode: {settings.DEBUG}")
    print(f"🌐 Host: {settings.HOST}:{settings.PORT}")
    print("")
    print("🔐 SECURITY CONFIGURATION:")
    print(f"   🔑 SECRET_KEY: {settings.SECRET_KEY[:20]}... (length: {len(settings.SECRET_KEY)})")
    print(f"   🔐 ALGORITHM: {settings.ALGORITHM}")
    print(f"   ⏰ TOKEN EXPIRY: {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutes")
    print("")
    print("🗄️  DATABASE:")
    # Hide password in DATABASE_URL for security
    db_url_safe = settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else "configured"
    print(f"   📍 Connected to: ...@{db_url_safe}")
    print("")
    print("🌍 CORS CONFIGURATION:")
    print(f"   Origins: {settings.CORS_ORIGINS}")
    print(f"   Credentials: {settings.CORS_CREDENTIALS}")
    print("")
    print("=" * 80)
    print("✅ Application started successfully!")
    print("=" * 80)
    print("")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
