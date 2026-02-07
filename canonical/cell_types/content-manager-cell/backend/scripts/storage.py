"""
Storage abstraction for content binaries.

Provides:
- CloudflareR2Storage: Cloudflare R2 storage with presigned URLs
- LocalStorage: Local filesystem storage fallback
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def upload(self, content_id: str, binary: bytes, filename: str, mime_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Upload binary content.

        Args:
            content_id: Unique content identifier
            binary: Raw binary data
            filename: Original filename
            mime_type: MIME type
            metadata: Optional metadata to attach to the upload

        Returns:
            data_ref: Storage reference (e.g., "r2://bucket/path" or "file:///path")
        """
        pass
    
    @abstractmethod
    def get_presigned_url(self, content_id: str, filename: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate presigned URL for direct download.
        
        Args:
            content_id: Content identifier
            filename: Original filename
            expires_in: URL expiration time in seconds
            
        Returns:
            Presigned URL or None if not supported
        """
        pass
    
    @abstractmethod
    def download(self, content_id: str, filename: str) -> Optional[bytes]:
        """
        Download binary content.
        
        Args:
            content_id: Content identifier
            filename: Original filename
            
        Returns:
            Binary data or None if not found
        """
        pass
    
    @abstractmethod
    def delete(self, content_id: str, filename: str) -> bool:
        """
        Delete content from storage.
        
        Args:
            content_id: Content identifier
            filename: Original filename
            
        Returns:
            True if deleted, False if not found
        """
        pass


class LocalStorage(StorageBackend):
    """
    Local filesystem storage backend.
    
    Stores files in a local directory structure:
    {base_path}/{content_type}/{content_id}/{filename}
    """
    
    def __init__(self, base_path: str = "/data/content"):
        """
        Initialize local storage.
        
        Args:
            base_path: Base directory for storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorage initialized: {self.base_path}")
    
    def _get_file_path(self, content_id: str, filename: str) -> Path:
        """Get full file path for content."""
        return self.base_path / content_id / filename
    
    def upload(self, content_id: str, binary: bytes, filename: str, mime_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Upload file to local storage."""
        file_path = self._get_file_path(content_id, filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_bytes(binary)

        # Save metadata companion file if provided
        if metadata:
            import json
            meta_path = Path(str(file_path) + ".meta")
            meta_path.write_text(json.dumps(metadata, indent=2, default=str))

        logger.info(f"Uploaded to local storage: {file_path}")

        return f"file://{file_path}"
    
    def get_presigned_url(self, content_id: str, filename: str, expires_in: int = 3600) -> Optional[str]:
        """Local storage doesn't support presigned URLs."""
        return None
    
    def download(self, content_id: str, filename: str) -> Optional[bytes]:
        """Download file from local storage."""
        file_path = self._get_file_path(content_id, filename)
        
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return None
        
        return file_path.read_bytes()
    
    def delete(self, content_id: str, filename: str) -> bool:
        """Delete file from local storage."""
        file_path = self._get_file_path(content_id, filename)
        
        if not file_path.exists():
            return False
        
        file_path.unlink()
        
        # Clean up empty directories
        try:
            file_path.parent.rmdir()
        except OSError:
            pass
        
        logger.info(f"Deleted from local storage: {file_path}")
        return True


class CloudflareR2Storage(StorageBackend):
    """
    Cloudflare R2 storage backend using boto3.
    
    Provides S3-compatible storage with presigned URL support.
    """
    
    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        endpoint_url: Optional[str] = None,
        public_url: Optional[str] = None
    ):
        """
        Initialize R2 storage.
        
        Args:
            account_id: Cloudflare account ID
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key
            bucket_name: R2 bucket name
            endpoint_url: Custom endpoint URL (auto-generated if None)
            public_url: Public URL for the bucket (for custom domains)
        """
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise ImportError(
                "boto3 is required for R2 storage. Install with: pip install boto3"
            )
        
        self.bucket_name = bucket_name
        self.public_url = public_url
        
        # Generate endpoint URL if not provided
        if endpoint_url is None:
            endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        
        self.endpoint_url = endpoint_url
        
        # Configure boto3 client
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(signature_version='s3v4')
        )
        
        logger.info(f"CloudflareR2Storage initialized: bucket={bucket_name}")
    
    def _get_object_key(self, content_id: str, filename: str) -> str:
        """Generate S3 object key for content."""
        return f"content/{content_id}/{filename}"
    
    def upload(self, content_id: str, binary: bytes, filename: str, mime_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Upload file to R2 with metadata."""
        object_key = self._get_object_key(content_id, filename)

        # Prepare metadata as custom S3 headers
        metadata_headers = {}
        if metadata:
            for key, value in metadata.items():
                # S3 allows custom headers with "x-amz-meta-" prefix
                metadata_headers[f"x-amz-meta-{key.lower()}"] = str(value)

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=object_key,
            Body=binary,
            ContentType=mime_type,
            Metadata=metadata_headers if metadata_headers else None
        )

        logger.info(f"Uploaded to R2: {object_key}")
        return f"r2://{self.bucket_name}/{object_key}"
    
    def get_presigned_url(self, content_id: str, filename: str, expires_in: int = 3600) -> Optional[str]:
        """Generate presigned URL for R2 object."""
        object_key = self._get_object_key(content_id, filename)
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_key
                },
                ExpiresIn=expires_in
            )
            
            # Replace endpoint URL with public URL if configured
            if self.public_url:
                url = url.replace(self.endpoint_url, self.public_url)
            
            return url
        except Exception as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None
    
    def download(self, content_id: str, filename: str) -> Optional[bytes]:
        """Download file from R2."""
        object_key = self._get_object_key(content_id, filename)
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Error downloading from R2: {e}")
            return None
    
    def delete(self, content_id: str, filename: str) -> bool:
        """Delete file from R2."""
        object_key = self._get_object_key(content_id, filename)
        
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            logger.info(f"Deleted from R2: {object_key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting from R2: {e}")
            return False


def get_storage_backend() -> StorageBackend:
    """
    Get configured storage backend based on environment variables.
    
    Returns:
        StorageBackend instance (CloudflareR2Storage or LocalStorage)
    """
    storage_mode = os.getenv("STORAGE_MODE", "local").lower()
    
    if storage_mode == "r2":
        # Check R2 configuration
        r2_enabled = os.getenv("R2_ENABLED", "false").lower() == "true"
        
        if not r2_enabled:
            logger.warning("R2 mode requested but R2_ENABLED=false. Falling back to local storage.")
            return LocalStorage(os.getenv("STORAGE_LOCAL_PATH", "/data/content"))
        
        # Get R2 credentials
        account_id = os.getenv("R2_ACCOUNT_ID")
        access_key_id = os.getenv("R2_ACCESS_KEY_ID")
        secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
        bucket_name = os.getenv("R2_BUCKET_NAME", "scareverse-content")
        endpoint_url = os.getenv("R2_ENDPOINT_URL")
        public_url = os.getenv("R2_PUBLIC_URL")
        
        if not all([account_id, access_key_id, secret_access_key]):
            logger.error("R2 credentials not configured. Falling back to local storage.")
            return LocalStorage(os.getenv("STORAGE_LOCAL_PATH", "/data/content"))
        
        try:
            return CloudflareR2Storage(
                account_id=account_id,
                access_key_id=access_key_id,
                secret_access_key=secret_access_key,
                bucket_name=bucket_name,
                endpoint_url=endpoint_url,
                public_url=public_url
            )
        except Exception as e:
            logger.error(f"Failed to initialize R2 storage: {e}. Falling back to local storage.")
            return LocalStorage(os.getenv("STORAGE_LOCAL_PATH", "/data/content"))
    
    # Default to local storage
    return LocalStorage(os.getenv("STORAGE_LOCAL_PATH", "/data/content"))
