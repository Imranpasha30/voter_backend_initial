import requests
import base64
from typing import List, Dict
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class ImageKitService:
    def __init__(self):
        self.private_key = settings.IMAGEKIT_PRIVATE_KEY
        self.url_endpoint = settings.IMAGEKIT_URL_ENDPOINT
        self.base_api_url = "https://api.imagekit.io/v1"
        
        # Create auth header
        auth_string = f"{self.private_key}:"
        encoded = base64.b64encode(auth_string.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded}",
        }

    def _fetch_all_files(self, max_limit=1000) -> List[Dict]:
        """Fetch all files from ImageKit using pagination"""
        all_files = []
        skip = 0
        limit = 100
        
        while skip < max_limit:
            params = {
                "skip": skip,
                "limit": limit,
            }
            
            response = requests.get(f"{self.base_api_url}/files", headers=self.headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"ImageKit API error: {response.status_code} - {response.text}")
                break
            
            batch = response.json()
            
            if not batch:
                break
            
            all_files.extend(batch)
            
            if len(batch) < limit:
                break
            
            skip += limit
        
        return all_files

    def list_folders(self) -> List[Dict]:
        """
        List all child folders inside base path
        Works by fetching all files and grouping them by folder
        """
        try:
            base_path = settings.IMAGEKIT_FOLDER_PATH
            print(f"📁 Listing folders in: {base_path}")

            # Fetch all files
            all_files = self._fetch_all_files()
            print(f"✅ Fetched {len(all_files)} total files from ImageKit")

            folders: dict[str, Dict] = {}

            for f in all_files:
                file_path = f.get('filePath', '')
                
                # Only process files in our base path
                if not file_path.startswith(base_path):
                    continue
                
                parts = file_path.split("/")
                
                # Find the subfolder after base_path
                # Example: /VoterConnectImages/VoterCard/19/file.pdf
                # base_path = /VoterConnectImages/VoterCard (2 parts after root)
                # We want parts[3] = "19"
                
                base_parts_count = len([p for p in base_path.split('/') if p])  # Count non-empty parts
                
                if len(parts) > base_parts_count + 1:  # +1 for the subfolder
                    folder_name = parts[base_parts_count + 1]
                    folder_full_path = f"{base_path}/{folder_name}"

                    if folder_full_path not in folders:
                        folders[folder_full_path] = {
                            "folder_path": folder_full_path,
                            "folder_name": folder_name,
                            "file_count": 0,
                            "thumbnail_url": None,
                        }

                    # Only count PDFs
                    if f.get('name', '').lower().endswith(".pdf"):
                        folders[folder_full_path]["file_count"] += 1
                        if not folders[folder_full_path]["thumbnail_url"]:
                            folders[folder_full_path]["thumbnail_url"] = f.get('thumbnail') or f.get('url')

            folder_list = list(folders.values())
            folder_list.sort(key=lambda x: x["folder_name"])
            
            print(f"✅ Found {len(folder_list)} folders with PDFs")
            for folder in folder_list:
                print(f"   📁 {folder['folder_name']}: {folder['file_count']} PDFs")
            
            return folder_list

        except Exception as e:
            logger.exception("Error listing folders from ImageKit")
            return []

    def list_files_in_folder(self, folder_path: str, skip: int = 0, limit: int = 20) -> Dict:
        """
        List PDF files in a specific folder with pagination
        """
        try:
            print(f"📄 Listing files in: {folder_path} (skip={skip}, limit={limit})")

            # Fetch all files
            all_files = self._fetch_all_files()
            
            # Filter files in this specific folder
            folder_files = []
            for f in all_files:
                fpath = f.get('filePath', '')
                name = f.get('name', '')
                
                # Check if file is in this exact folder (not subfolders)
                if fpath.startswith(folder_path + '/') and name.lower().endswith('.pdf'):
                    # Count slashes to ensure it's directly in folder, not in subfolder
                    relative = fpath[len(folder_path)+1:]  # Remove folder path + /
                    if '/' not in relative:  # No more slashes = direct child
                        folder_files.append(f)
            
            # Sort by name
            folder_files.sort(key=lambda x: x.get('name', ''))
            
            # Apply pagination
            total = len(folder_files)
            paginated_files = folder_files[skip:skip+limit]
            
            pdfs: List[Dict] = []
            for f in paginated_files:
                pdfs.append({
                    "file_id": f.get('fileId', ''),
                    "file_name": f.get('name', ''),
                    "file_url": f.get('url', ''),
                    "thumbnail_url": f.get('thumbnail') or f.get('url', ''),
                    "file_size": f.get('size', 0),
                    "created_at": f.get('createdAt', ''),
                })

            page = (skip // limit) + 1
            total_pages = max(1, (total + limit - 1) // limit)

            print(f"✅ Found {total} total PDFs in folder, showing page {page} ({len(pdfs)} files)")

            return {
                "files": pdfs,
                "total": total,
                "page": page,
                "page_size": limit,
                "total_pages": total_pages,
            }

        except Exception as e:
            logger.exception("Error listing files from ImageKit")
            return {
                "files": [],
                "total": 0,
                "page": 1,
                "page_size": limit,
                "total_pages": 0,
            }

    def search_files(self, folder_path: str, query: str) -> List[Dict]:
        """
        Search PDF files in a specific folder by name
        """
        try:
            print(f"🔍 Searching in: {folder_path}, query='{query}'")

            # Fetch all files
            all_files = self._fetch_all_files()
            
            pdfs: List[Dict] = []

            for f in all_files:
                fpath = f.get('filePath', '')
                name = f.get('name', '')
                
                # Check if in folder and matches query
                if fpath.startswith(folder_path + '/') and name.lower().endswith(".pdf"):
                    if query.lower() in name.lower():
                        pdfs.append({
                            "file_id": f.get('fileId', ''),
                            "file_name": name,
                            "file_url": f.get('url', ''),
                            "thumbnail_url": f.get('thumbnail') or f.get('url', ''),
                            "file_size": f.get('size', 0),
                            "created_at": f.get('createdAt', ''),
                        })

            print(f"✅ Found {len(pdfs)} matching PDFs")
            return pdfs

        except Exception as e:
            logger.exception("Error searching files in ImageKit")
            return []


imagekit_service = ImageKitService()
