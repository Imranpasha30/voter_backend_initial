from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict

from app.db.session import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.services.imagekit_service import imagekit_service
from app.core.config import settings

router = APIRouter()


@router.get("/folders")
def get_document_folders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all document folders from ImageKit
    """
    print(f"\n{'='*60}")
    print(f"📁 FETCHING DOCUMENT FOLDERS")
    print(f"{'='*60}")
    print(f"👤 User: {current_user.full_name} (ID: {current_user.user_id})")
    
    try:
        folders = imagekit_service.list_folders()
        
        print(f"✅ Found {len(folders)} folders")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "folders": folders
        }
    
    except Exception as e:
        print(f"❌ Error fetching folders: {e}")
        print(f"{'='*60}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch folders: {str(e)}"
        )


@router.get("/files")
def get_document_files(
    folder_path: str = Query(..., description="Folder path to list files from"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get PDF files in a specific folder with pagination
    """
    print(f"\n{'='*60}")
    print(f"📄 FETCHING FILES FROM FOLDER")
    print(f"{'='*60}")
    print(f"📁 Folder: {folder_path}")
    print(f"📄 Page: {page}, Size: {page_size}")
    
    try:
        skip = (page - 1) * page_size
        result = imagekit_service.list_files_in_folder(
            folder_path=folder_path,
            skip=skip,
            limit=page_size
        )
        
        print(f"✅ Found {len(result['files'])} files")
        print(f"{'='*60}\n")
        
        return result
    
    except Exception as e:
        print(f"❌ Error fetching files: {e}")
        print(f"{'='*60}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch files: {str(e)}"
        )


@router.get("/search")
def search_documents(
    folder_path: str = Query(..., description="Folder path to search in"),
    query: str = Query(..., min_length=1, description="Search query"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search for PDF files in a folder
    """
    print(f"\n{'='*60}")
    print(f"🔍 SEARCHING DOCUMENTS")
    print(f"{'='*60}")
    print(f"📁 Folder: {folder_path}")
    print(f"🔎 Query: {query}")
    
    try:
        files = imagekit_service.search_files(
            folder_path=folder_path,
            query=query
        )
        
        print(f"✅ Found {len(files)} matching files")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "files": files,
            "total": len(files)
        }
    
    except Exception as e:
        print(f"❌ Error searching files: {e}")
        print(f"{'='*60}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search files: {str(e)}"
        )
    

@router.get("/test-all-files")
def test_all_files(
    current_user: User = Depends(get_current_user),
):
    """
    Get ALL files from ImageKit to see actual paths
    """
    import requests
    import base64
    
    try:
        private_key = settings.IMAGEKIT_PRIVATE_KEY
        auth_string = f"{private_key}:"
        encoded = base64.b64encode(auth_string.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded}",
        }
        
        base_url = "https://api.imagekit.io/v1/files"
        
        print("\n" + "="*60)
        print("🔍 FETCHING ALL FILES FROM IMAGEKIT")
        print("="*60)
        
        # Get ALL files (no path filter)
        all_files = []
        skip = 0
        limit = 100
        
        while True:
            params = {
                "skip": skip,
                "limit": limit,
            }
            
            response = requests.get(base_url, headers=headers, params=params)
            
            if response.status_code != 200:
                print(f"❌ Error: {response.status_code} - {response.text}")
                break
            
            batch = response.json()
            
            if not batch:
                break
            
            all_files.extend(batch)
            print(f"📦 Fetched {len(batch)} files (total: {len(all_files)})")
            
            if len(batch) < limit:
                break
            
            skip += limit
            
            # Safety limit
            if skip > 500:
                break
        
        print(f"\n✅ TOTAL FILES: {len(all_files)}")
        
        # Analyze paths
        folders = {}
        pdf_files = []
        
        for f in all_files:
            path = f.get('filePath', '')
            name = f.get('name', '')
            
            # Track PDFs
            if name.lower().endswith('.pdf'):
                pdf_files.append(f)
            
            # Extract folder
            parts = path.split('/')
            if len(parts) > 1:
                folder = '/'.join(parts[:-1])
                if folder not in folders:
                    folders[folder] = []
                folders[folder].append(name)
        
        print(f"\n📄 TOTAL PDFs: {len(pdf_files)}")
        print(f"📂 TOTAL FOLDERS: {len(folders)}")
        
        print(f"\n📂 ALL FOLDERS:")
        for folder in sorted(folders.keys()):
            print(f"   {folder}: {len(folders[folder])} files")
        
        print(f"\n📄 ALL PDF PATHS:")
        for pdf in pdf_files[:20]:
            print(f"   {pdf.get('filePath')}")
        
        print("="*60 + "\n")
        
        return {
            "success": True,
            "total_files": len(all_files),
            "total_pdfs": len(pdf_files),
            "total_folders": len(folders),
            "folders": {k: len(v) for k, v in folders.items()},
            "pdf_paths": [p.get('filePath') for p in pdf_files[:20]],
            "all_files_sample": [{"path": f.get('filePath'), "name": f.get('name')} for f in all_files[:30]]
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
