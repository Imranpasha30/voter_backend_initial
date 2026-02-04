import requests
import base64
from typing import List, Dict, Optional
from functools import lru_cache
from datetime import datetime, timedelta
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class ImageKitCache:
    """Simple in-memory cache with expiry"""
    def __init__(self, expiry_minutes: int = 10):
        self._cache: Dict[str, tuple] = {}
        self.expiry_minutes = expiry_minutes
    
    def get(self, key: str) -> Optional[any]:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < timedelta(minutes=self.expiry_minutes):
                logger.info(f"✅ Cache HIT: {key}")
                return value
            else:
                del self._cache[key]
                logger.info(f"❌ Cache EXPIRED: {key}")
        return None
    
    def set(self, key: str, value: any):
        self._cache[key] = (value, datetime.now())
        logger.info(f"💾 Cache SET: {key}")
    
    def clear(self):
        self._cache.clear()
        logger.info("🗑️  Cache CLEARED")


class ImageKitService:
    def __init__(self):
        self.private_key = settings.IMAGEKIT_PRIVATE_KEY
        self.url_endpoint = settings.IMAGEKIT_URL_ENDPOINT
        self.base_api_url = "https://api.imagekit.io/v1"
        self.cache = ImageKitCache(expiry_minutes=10)
        
        # Create auth header
        auth_string = f"{self.private_key}:"
        encoded = base64.b64encode(auth_string.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
        }

    def _make_request(
        self, 
        endpoint: str, 
        params: Dict = None, 
        method: str = "GET"
    ) -> Dict:
        """Centralized request handler with error handling"""
        try:
            url = f"{self.base_api_url}{endpoint}"
            
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
            else:
                response = requests.post(url, headers=self.headers, json=params, timeout=30)
            
            response.raise_for_status()
            return {"success": True, "data": response.json()}
            
        except requests.exceptions.Timeout:
            logger.error(f"⏱️  Request timeout: {endpoint}")
            return {"success": False, "error": "Request timeout", "code": 408}
        except requests.exceptions.ConnectionError:
            logger.error(f"🔌 Connection error: {endpoint}")
            return {"success": False, "error": "Connection error", "code": 503}
        except requests.exceptions.HTTPError as e:
            logger.error(f"🚫 HTTP error {e.response.status_code}: {endpoint}")
            return {
                "success": False, 
                "error": f"HTTP {e.response.status_code}", 
                "code": e.response.status_code
            }
        except Exception as e:
            logger.exception(f"❌ Unexpected error: {endpoint}")
            return {"success": False, "error": str(e), "code": 500}

    def _fetch_all_files_cached(self, max_limit: int = 5000) -> List[Dict]:
        """Fetch all files with caching - CRITICAL for performance"""
        cache_key = "all_files"
        
        # Try cache first
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        # Fetch from API
        logger.info("📡 Fetching files from ImageKit API...")
        all_files = []
        skip = 0
        limit = 100
        
        while skip < max_limit:
            params = {"skip": skip, "limit": limit}
            result = self._make_request("/files", params=params)
            
            if not result["success"]:
                logger.error(f"Failed to fetch files: {result.get('error')}")
                break
            
            batch = result["data"]
            if not batch:
                break
            
            all_files.extend(batch)
            logger.info(f"  📦 Fetched batch: {len(batch)} files (total: {len(all_files)})")
            
            if len(batch) < limit:
                break
            
            skip += limit
        
        logger.info(f"✅ Total files fetched: {len(all_files)}")
        
        # Cache the result
        self.cache.set(cache_key, all_files)
        
        return all_files

    def list_folders(self) -> List[Dict]:
        """
        List folder names and PDF counts only (fast & lightweight)
        Uses cached file data for maximum performance
        """
        try:
            base_path = settings.IMAGEKIT_FOLDER_PATH
            logger.info(f"\n{'='*60}")
            logger.info(f"📁 LISTING FOLDERS in: {base_path}")
            logger.info(f"{'='*60}")

            # Get all files (cached)
            all_files = self._fetch_all_files_cached()
            
            if not all_files:
                logger.warning("⚠️  No files found")
                return []

            folders: Dict[str, Dict] = {}
            base_parts_count = len([p for p in base_path.split('/') if p])

            for file in all_files:
                file_path = file.get('filePath', '')
                
                if not file_path.startswith(base_path):
                    continue
                
                parts = file_path.split("/")
                
                # Extract folder name
                if len(parts) > base_parts_count + 1:
                    folder_name = parts[base_parts_count + 1]
                    folder_full_path = f"{base_path}/{folder_name}"

                    if folder_full_path not in folders:
                        folders[folder_full_path] = {
                            "folder_path": folder_full_path,
                            "folder_name": folder_name,
                            "file_count": 0,
                        }

                    # Count only PDFs
                    if file.get('name', '').lower().endswith(".pdf"):
                        folders[folder_full_path]["file_count"] += 1

            folder_list = list(folders.values())
            folder_list.sort(key=lambda x: x["folder_name"])
            
            logger.info(f"✅ Found {len(folder_list)} folders")
            for folder in folder_list:
                logger.info(f"   📁 {folder['folder_name']}: {folder['file_count']} PDFs")
            logger.info(f"{'='*60}\n")
            
            return folder_list

        except Exception as e:
            logger.exception("❌ Error listing folders")
            return []

    def list_files_in_folder(
        self, 
        folder_path: str, 
        skip: int = 0, 
        limit: int = 20
    ) -> Dict:
        """
        List PDF files in a folder with TRUE server-side pagination
        Uses cached data and applies pagination in-memory
        """
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"📄 FETCHING FILES FROM: {folder_path}")
            logger.info(f"   Page: {(skip//limit)+1}, Skip: {skip}, Limit: {limit}")
            logger.info(f"{'='*60}")

            # Get all files (cached)
            all_files = self._fetch_all_files_cached()
            
            # Filter files in this specific folder
            folder_files = []
            for file in all_files:
                file_path = file.get('filePath', '')
                file_name = file.get('name', '')
                
                if file_path.startswith(folder_path + '/') and file_name.lower().endswith('.pdf'):
                    relative = file_path[len(folder_path)+1:]
                    if '/' not in relative:  # Direct child only
                        folder_files.append(file)
            
            # Sort by name
            folder_files.sort(key=lambda x: x.get('name', ''))
            
            # Calculate pagination
            total = len(folder_files)
            paginated_files = folder_files[skip:skip+limit]
            
            # Transform to response format
            pdfs: List[Dict] = []
            for file in paginated_files:
                pdfs.append({
                    "file_id": file.get('fileId', ''),
                    "file_name": file.get('name', ''),
                    "file_url": file.get('url', ''),
                    "thumbnail_url": file.get('thumbnail') or file.get('url', ''),
                    "file_size": file.get('size', 0),
                    "created_at": file.get('createdAt', ''),
                })

            page = (skip // limit) + 1
            total_pages = max(1, (total + limit - 1) // limit)

            logger.info(f"✅ Returning page {page}/{total_pages}: {len(pdfs)} files")
            logger.info(f"{'='*60}\n")

            return {
                "files": pdfs,
                "total": total,
                "page": page,
                "page_size": limit,
                "total_pages": total_pages,
            }

        except Exception as e:
            logger.exception("❌ Error listing files")
            return {
                "files": [],
                "total": 0,
                "page": 1,
                "page_size": limit,
                "total_pages": 0,
            }

    def search_files(self, folder_path: str, query: str) -> List[Dict]:
        """
        Search PDF files in a folder (case-insensitive)
        Uses cached data for instant results
        """
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 SEARCHING IN: {folder_path}")
            logger.info(f"   Query: '{query}'")
            logger.info(f"{'='*60}")

            # Get all files (cached)
            all_files = self._fetch_all_files_cached()
            
            pdfs: List[Dict] = []
            query_lower = query.lower()

            for file in all_files:
                file_path = file.get('filePath', '')
                file_name = file.get('name', '')
                
                if file_path.startswith(folder_path + '/') and file_name.lower().endswith(".pdf"):
                    if query_lower in file_name.lower():
                        pdfs.append({
                            "file_id": file.get('fileId', ''),
                            "file_name": file_name,
                            "file_url": file.get('url', ''),
                            "thumbnail_url": file.get('thumbnail') or file.get('url', ''),
                            "file_size": file.get('size', 0),
                            "created_at": file.get('createdAt', ''),
                        })

            logger.info(f"✅ Found {len(pdfs)} matching PDFs")
            logger.info(f"{'='*60}\n")
            
            return pdfs

        except Exception as e:
            logger.exception("❌ Error searching files")
            return []

    def clear_cache(self):
        """Clear the cache - useful for testing or force refresh"""
        self.cache.clear()


# Singleton instance
imagekit_service = ImageKitService()
