from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Dict

from app.db.session import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.services.imagekit_service import imagekit_service
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/folders", response_model=Dict)
def get_document_folders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all document folders from ImageKit
    - Fast & cached
    - Returns folder names and PDF counts only
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"📁 API: GET /folders")
    logger.info(f"👤 User: {current_user.full_name} (ID: {current_user.user_id})")
    logger.info(f"{'='*70}")
    
    try:
        folders = imagekit_service.list_folders()
        
        logger.info(f"✅ API Response: {len(folders)} folders")
        logger.info(f"{'='*70}\n")
        
        return {
            "success": True,
            "folders": folders,
            "total": len(folders)
        }
    
    except Exception as e:
        logger.exception("❌ API Error in get_document_folders")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch folders: {str(e)}"
        )


@router.get("/files", response_model=Dict)
def get_document_files(
    folder_path: str = Query(..., description="Folder path to list files from"),
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get PDF files in a specific folder with pagination
    - True server-side pagination
    - Cached for performance
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"📄 API: GET /files")
    logger.info(f"📁 Folder: {folder_path}")
    logger.info(f"📄 Page: {page}, Size: {page_size}")
    logger.info(f"{'='*70}")
    
    try:
        skip = (page - 1) * page_size
        result = imagekit_service.list_files_in_folder(
            folder_path=folder_path,
            skip=skip,
            limit=page_size
        )
        
        logger.info(f"✅ API Response: {len(result['files'])} files, Page {result['page']}/{result['total_pages']}")
        logger.info(f"{'='*70}\n")
        
        return result
    
    except Exception as e:
        logger.exception("❌ API Error in get_document_files")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch files: {str(e)}"
        )


@router.get("/search", response_model=Dict)
def search_documents(
    folder_path: str = Query(..., description="Folder path to search in"),
    query: str = Query(..., min_length=1, description="Search query"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search for PDF files in a folder
    - Case-insensitive search
    - Instant results (cached data)
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"🔍 API: GET /search")
    logger.info(f"📁 Folder: {folder_path}")
    logger.info(f"🔎 Query: '{query}'")
    logger.info(f"{'='*70}")
    
    try:
        files = imagekit_service.search_files(
            folder_path=folder_path,
            query=query
        )
        
        logger.info(f"✅ API Response: {len(files)} matching files")
        logger.info(f"{'='*70}\n")
        
        return {
            "success": True,
            "files": files,
            "total": len(files)
        }
    
    except Exception as e:
        logger.exception("❌ API Error in search_documents")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search files: {str(e)}"
        )


@router.post("/cache/clear")
def clear_cache(
    current_user: User = Depends(get_current_user),
):
    """
    Clear ImageKit cache - useful for testing or force refresh
    """
    logger.info(f"🗑️  Clearing ImageKit cache (User: {current_user.full_name})")
    
    try:
        imagekit_service.clear_cache()
        
        return {
            "success": True,
            "message": "Cache cleared successfully"
        }
    
    except Exception as e:
        logger.exception("❌ Error clearing cache")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}"
        )
