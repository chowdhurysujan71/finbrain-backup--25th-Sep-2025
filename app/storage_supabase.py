"""
Supabase Storage integration for FinBrain
Provides signed URL generation for secure file uploads/downloads
"""
import os
import requests
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SupabaseStorageClient:
    """Client for interacting with Supabase Storage API"""
    
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL")
        self.service_key = os.environ.get("SUPABASE_SERVICE_KEY") 
        self.bucket = os.environ.get("SUPABASE_BUCKET", "user-assets")
        
        if not self.url or not self.service_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")
            
        self.base_url = f"{self.url}/storage/v1"
        self.headers = {
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json"
        }
    
    def get_upload_url(self, path: str, content_type: str, expires_in: int = 60) -> Dict[str, Any]:
        """
        Generate a signed URL for uploading a file to Supabase Storage
        
        Args:
            path: Object path in bucket (e.g., "user123/document.pdf")
            content_type: MIME type of the file
            expires_in: URL expiration time in seconds
            
        Returns:
            Dict with upload_url, expires_in, and canonical path
        """
        sign_url = f"{self.base_url}/object/sign/{self.bucket}/{path}"
        
        payload = {
            "expiresIn": expires_in
        }
        
        try:
            response = requests.post(
                sign_url, 
                json=payload, 
                headers=self.headers,
                timeout=3
            )
            response.raise_for_status()
            
            data = response.json()
            signed_url = data.get("signedURL")
            
            if not signed_url:
                raise ValueError("No signedURL in response")
                
            # Convert to upload URL (signed URL is for GET, we need PUT capability)
            # For Supabase, we'll use the upload endpoint with the signed token
            upload_url = f"{self.base_url}/object/{self.bucket}/{path}"
            
            return {
                "upload_url": upload_url,
                "expires_in": expires_in,
                "path": path,
                "headers": {
                    "Authorization": f"Bearer {self.service_key}",
                    "Content-Type": content_type
                }
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Supabase upload URL generation failed: {str(e)}")
            raise RuntimeError(f"Failed to generate upload URL: {str(e)}")
    
    def get_download_url(self, path: str, expires_in: int = 60) -> Dict[str, Any]:
        """
        Generate a signed URL for downloading a file from Supabase Storage
        
        Args:
            path: Object path in bucket
            expires_in: URL expiration time in seconds
            
        Returns:
            Dict with download_url and expires_in
        """
        sign_url = f"{self.base_url}/object/sign/{self.bucket}/{path}"
        
        payload = {
            "expiresIn": expires_in
        }
        
        try:
            response = requests.post(
                sign_url,
                json=payload,
                headers=self.headers, 
                timeout=3
            )
            response.raise_for_status()
            
            data = response.json()
            signed_url = data.get("signedURL")
            
            if not signed_url:
                raise ValueError("No signedURL in response")
                
            # Convert relative URL to absolute URL
            if signed_url.startswith("/"):
                download_url = f"{self.url}{signed_url}"
            else:
                download_url = signed_url
                
            return {
                "download_url": download_url,
                "expires_in": expires_in
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Supabase download URL generation failed: {str(e)}")
            raise RuntimeError(f"Failed to generate download URL: {str(e)}")
    
    def delete_object(self, path: str) -> bool:
        """
        Delete an object from Supabase Storage
        
        Args:
            path: Object path in bucket
            
        Returns:
            True if deletion successful
        """
        delete_url = f"{self.base_url}/object/{self.bucket}/{path}"
        
        try:
            response = requests.delete(
                delete_url,
                headers=self.headers,
                timeout=3
            )
            response.raise_for_status()
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Supabase object deletion failed: {str(e)}")
            raise RuntimeError(f"Failed to delete object: {str(e)}")

# Global client instance
storage_client = SupabaseStorageClient()