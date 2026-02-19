import requests
import base64
from typing import List, Dict, Optional
from functools import lru_cache
from datetime import datetime, timedelta
from app.core.config import settings
import logging
import io


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

    def _fetch_all_files_cached(self, max_limit: int = 100000) -> List[Dict]:
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

    def _fetch_subfolders_from_api(self, folder_path: str) -> List[Dict]:
        """
        Fetch subfolders directly from ImageKit API
        This will show even empty folders
        """
        try:
            logger.info(f"🔍 Fetching subfolders from API: {folder_path}")
            
            # ImageKit folder details endpoint
            url = f"{self.base_api_url}/folder"
            params = {"path": folder_path}
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                subfolders = []
                
                # Extract folder names from response
                if isinstance(data, dict) and 'folders' in data:
                    for folder in data['folders']:
                        folder_name = folder.get('name', '')
                        if folder_name:
                            subfolders.append({
                                'name': folder_name,
                                'path': f"{folder_path}/{folder_name}"
                            })
                
                logger.info(f"✅ Found {len(subfolders)} subfolders via API")
                return subfolders
            else:
                logger.warning(f"⚠️ API returned status {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error fetching subfolders from API: {e}")
            return []

    def list_folders(self, base_path: str = None, include_empty: bool = True) -> List[Dict]:
        """
        List folder names and PDF counts only (fast & lightweight)
        Uses cached file data for maximum performance
        
        Args:
            base_path: Optional custom base path. If None, uses default from settings.
            include_empty: If True, will fetch empty folders from API
        """
        try:
            # ✅ Use provided base_path or default
            if base_path is None:
                base_path = settings.IMAGEKIT_FOLDER_PATH
                
            logger.info(f"\n{'='*60}")
            logger.info(f"📁 LISTING FOLDERS in: {base_path}")
            logger.info(f"{'='*60}")

            # Get all files (cached)
            all_files = self._fetch_all_files_cached()
            
            folders: Dict[str, Dict] = {}
            base_parts_count = len([p for p in base_path.split('/') if p])

            # Count files in each subfolder
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

            # ✅ NEW: If no folders found and include_empty is True, try API
            if not folders and include_empty:
                logger.info("⚠️ No folders found in cache, checking API for empty folders...")
                api_folders = self._fetch_subfolders_from_api(base_path)
                
                for api_folder in api_folders:
                    folders[api_folder['path']] = {
                        "folder_path": api_folder['path'],
                        "folder_name": api_folder['name'],
                        "file_count": 0,
                    }

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


    def upload_user_profile_image(
        self,
        file_bytes: bytes,
        file_name: str,
        user_id: int,
    ) -> Dict:
        """
        Upload a user profile image to ImageKit.
        Stores under /VoterConnectImages/sharkify_user/{user_id}/
        Returns the uploaded file's URL and fileId.
        """
        try:
            # Sanitize file name
            import re
            safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file_name)
            folder_path = f"{settings.IMAGEKIT_FOLDER_PATH_3}/{user_id}"

            logger.info(f"📤 Uploading profile image for user {user_id}")
            logger.info(f"   File: {safe_name} ({len(file_bytes)} bytes)")
            logger.info(f"   Folder: {folder_path}")

            # Encode file to base64
            encoded_file = base64.b64encode(file_bytes).decode('utf-8')

            # Build upload payload
            upload_url = "https://upload.imagekit.io/api/v1/files/upload"
            payload = {
                "file": encoded_file,
                "fileName": safe_name,
                "folder": folder_path,
                "useUniqueFileName": True,  # Prevents collisions
                "overwriteFile": False,
            }

            response = requests.post(
                upload_url,
                headers={
                    "Authorization": self.headers["Authorization"]
                    # ❌ Do NOT include Content-Type here — requests sets it for form data
                },
                data={
                    "file": encoded_file,
                    "fileName": safe_name,
                    "folder": folder_path,
                    "useUniqueFileName": "true",
                },
                timeout=60,
            )

            if response.status_code in (200, 201):
                data = response.json()
                file_url = data.get("url", "")
                file_id = data.get("fileId", "")

                logger.info(f"✅ Upload successful!")
                logger.info(f"   URL: {file_url}")
                logger.info(f"   FileId: {file_id}")

                # Invalidate cache so next list_folders() picks up new file
                self.cache.clear()

                return {
                    "success": True,
                    "url": file_url,
                    "file_id": file_id,
                    "file_name": data.get("name", safe_name),
                    "size": data.get("size", 0),
                }
            else:
                logger.error(f"❌ Upload failed: {response.status_code} — {response.text}")
                return {
                    "success": False,
                    "error": f"Upload failed with status {response.status_code}",
                    "detail": response.text,
                }

        except requests.exceptions.Timeout:
            logger.error("⏱️  Upload timeout")
            return {"success": False, "error": "Upload timed out"}
        except Exception as e:
            logger.exception("❌ Unexpected error during profile image upload")
            return {"success": False, "error": str(e)}


    def delete_file(self, file_id: str) -> Dict:
        """
        Delete a file from ImageKit by fileId.
        Used to remove old profile image when user uploads a new one.
        """
        try:
            if not file_id:
                return {"success": False, "error": "No file_id provided"}

            logger.info(f"🗑️  Deleting file: {file_id}")
            result = self._make_request(f"/files/{file_id}", method="DELETE_CALL")

            # requests.delete needs special handling
            url = f"{self.base_api_url}/files/{file_id}"
            response = requests.delete(url, headers=self.headers, timeout=30)

            if response.status_code in (200, 204):
                logger.info(f"✅ File deleted: {file_id}")
                self.cache.clear()
                return {"success": True}
            else:
                logger.error(f"❌ Delete failed: {response.status_code}")
                return {"success": False, "error": f"Delete failed: {response.status_code}"}

        except Exception as e:
            logger.exception("❌ Error deleting file")
            return {"success": False, "error": str(e)}




# Singleton instance
imagekit_service = ImageKitService()
