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
    base_path: str = Query(None, description="Optional custom base path"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all document folders from ImageKit
    - Fast & cached
    - Returns folder names and PDF counts only
    - Supports custom base_path via query parameter
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"📁 API: GET /folders")
    logger.info(f"👤 User: {current_user.full_name} (ID: {current_user.user_id})")
    logger.info(f"📂 Base Path: {base_path or 'default'}")
    logger.info(f"{'='*70}")
    
    try:
        folders = imagekit_service.list_folders(base_path=base_path)
        
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



@router.get("/debug/all-folders")
def debug_all_folders(
    current_user: User = Depends(get_current_user),
):
    """
    DEBUG: Show ALL folders in ImageKit to verify structure
    """
    try:
        all_files = imagekit_service._fetch_all_files_cached()
        
        # Get unique folder paths
        folder_paths = set()
        for file in all_files:
            file_path = file.get('filePath', '')
            if file_path:
                # Get all parent folders
                parts = file_path.split('/')
                for i in range(1, len(parts)):
                    folder_paths.add('/'.join(parts[:i]))
        
        # Filter for VoterConnectImages folders
        voter_folders = sorted([
            f for f in folder_paths 
            if f.startswith('/VoterConnectImages')
        ])
        
        # Get folder details
        folder_details = []
        for folder_path in voter_folders:
            # Count files in this folder
            file_count = len([
                f for f in all_files 
                if f.get('filePath', '').startswith(folder_path + '/')
                and f.get('name', '').lower().endswith('.pdf')
            ])
            
            folder_details.append({
                'path': folder_path,
                'file_count': file_count,
                'depth': folder_path.count('/'),
            })
        
        return {
            'success': True,
            'total_files': len(all_files),
            'total_folders': len(voter_folders),
            'folders': folder_details,
        }
    
    except Exception as e:
        logger.exception("❌ Debug error")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
