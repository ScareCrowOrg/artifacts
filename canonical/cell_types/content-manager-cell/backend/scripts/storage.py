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
        logger.info(f"[DEBUG] LocalStorage absolute base_path: {self.base_path.resolve()}")
    
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
        logger.info(f"[DIAG] LocalStorage.upload file_path (pre-resolve)={file_path}")
        resolved = file_path.resolve()
        logger.info(f"[DIAG] LocalStorage.upload file_path (post-resolve)={resolved}")

        # data_ref: relative path from artifacts/, NOT absolute /app/artifacts/...
        # This ensures MongoDB stores portable refs: file://artifacts/runtime/...
        # Frontend converts file:// → / → /artifacts/runtime/... (auth-proxy URL)
        ref_str = str(resolved)
        # DIAG: Log raw ref_str before /app/ stripping to debug prefix issues
        logger.info(f"[DIAG] storage.upload ref_str before strip: {ref_str}, starts_with_app={ref_str.startswith('/app/')}")
        if ref_str.startswith('/app/'):
            ref_str = ref_str[len('/app/'):]
            logger.info(f"[DIAG] storage.upload ref_str after /app/ strip: {ref_str}")
        else:
            logger.info(f"[DIAG] storage.upload ref_str does NOT start with /app/ — no strip applied")
        # PERMANENTE: Log final data_ref — critical for debugging file:// prefix in handleLoad
        logger.warning(f"[PERMANENTE] storage.upload returning data_ref for content_id={content_id}, filename={filename}: file://{ref_str}")
        return f"file://{ref_str}"
    
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
        logger.debug(f"[DEBUG] CloudflareR2Storage initialized with:")
        logger.debug(f"[DEBUG]   - endpoint_url: {endpoint_url}")
        logger.debug(f"[DEBUG]   - bucket_name: {bucket_name}")
        logger.debug(f"[DEBUG]   - public_url: {public_url if public_url else '(not set)'}")
        logger.debug(f"[DEBUG]   - account_id used in endpoint: {account_id}")
    
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

        logger.debug(f"[DEBUG] R2 upload details:")
        logger.debug(f"[DEBUG]   - endpoint: {self.endpoint_url}")
        logger.debug(f"[DEBUG]   - bucket: {self.bucket_name}")
        logger.debug(f"[DEBUG]   - object_key: {object_key}")
        logger.debug(f"[DEBUG]   - content_size: {len(binary)} bytes")
        logger.debug(f"[DEBUG]   - content_type: {mime_type}")
        logger.debug(f"[DEBUG]   - metadata_headers: {list(metadata_headers.keys())}")

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=binary,
                ContentType=mime_type,
                Metadata=metadata_headers if metadata_headers else None
            )

            logger.info(f"Uploaded to R2: {object_key}")
            return f"r2://{self.bucket_name}/{object_key}"
        except Exception as e:
            logger.error(f"[DEBUG] R2 upload failed:")
            logger.error(f"[DEBUG]   - error_type: {type(e).__name__}")
            logger.error(f"[DEBUG]   - error_message: {str(e)}")
            logger.error(f"[DEBUG]   - endpoint_url: {self.endpoint_url}")
            logger.error(f"[DEBUG]   - bucket_name: {self.bucket_name}")
            logger.error(f"[DEBUG]   - object_key: {object_key}")
            raise
    
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


def get_storage_backend(assignee_id: str = None) -> StorageBackend:
    """
    Get configured storage backend based on environment variables.

    When assignee_id is provided, the local storage path is scoped to
    runtime/user/{assignee_id}/contents for per-user content isolation.

    STORAGE ARCHITECTURE (Local Runtime Magro):
    ------------------------------------------
    DEFAULT mode is "local" (STORAGE_MODE=local):
      - Files are saved to /app/artifacts/runtime/user/{assignee}/contents/{id}/{file}
      - The Runtime File Server (auth-proxy Rust) serves these files via HTTP
        with streaming zero-copy and access verification
      - This is the standard for locally-generated assets (PNG, GLB, etc.)

    R2 mode (STORAGE_MODE=r2) is OPTIONAL and intended for EXPLICIT PUBLISH:
      - Only activates when STORAGE_MODE=r2 AND R2_ENABLED=true AND credentials present
      - Intended for community sharing / galaxy-wide distribution
      - Local Runtime is the default; R2 is opt-in for publishing

    Args:
        assignee_id: Optional user identifier for runtime scoping

    Returns:
        StorageBackend instance (CloudflareR2Storage or LocalStorage)
    """
    storage_mode = os.getenv("STORAGE_MODE", "local").lower()
    logger.debug(f"[DEBUG] STORAGE_MODE={storage_mode}")

    # Determine base path: artifacts/runtime/user/{assignee}/contents if assignee_id provided
    # NOTE: 'artifacts/runtime' prefix aligns with Docker volume mount at /app/artifacts/runtime/
    # Without 'artifacts/' prefix, files would go to /app/runtime/... (inside container, not on host)
    if assignee_id:
        default_local_path = f"/app/artifacts/runtime/user/{assignee_id}/contents"
    else:
        default_local_path = "/data/content"

    if storage_mode == "r2":
        # Check R2 configuration
        r2_enabled = os.getenv("R2_ENABLED", "false").lower() == "true"
        logger.debug(f"[DEBUG] R2_ENABLED={r2_enabled}")

        if not r2_enabled:
            logger.warning("R2 mode requested but R2_ENABLED=false. Falling back to local storage.")
            local_path = os.getenv("STORAGE_LOCAL_PATH", default_local_path)
            logger.info(f"[DEBUG] Using LocalStorage (R2 fallback) at {local_path}")
            logger.info(f"[DEBUG] CWD when initializing storage (R2 fallback): {Path.cwd()}")
            resolved = Path(local_path).resolve()
            logger.info(f"[DEBUG] Resolved absolute path (R2 fallback): {resolved}")
            logger.info(f"[DEBUG] Volume mount check (R2 fallback) — does {resolved} exist? {resolved.exists()}")
            return LocalStorage(local_path)

        # Get R2 credentials
        account_id = os.getenv("R2_ACCOUNT_ID")
        access_key_id = os.getenv("R2_ACCESS_KEY_ID")
        secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
        bucket_name = os.getenv("R2_BUCKET_NAME", "scareverse-content")
        endpoint_url = os.getenv("R2_ENDPOINT_URL")
        public_url = os.getenv("R2_PUBLIC_URL")

        # Log R2 configuration (sanitized)
        logger.info(f"[DEBUG] R2 Configuration:")
        logger.info(f"[DEBUG]   - account_id: {'SET' if account_id else 'NOT SET'}")
        logger.info(f"[DEBUG]   - access_key_id: {'SET' if access_key_id else 'NOT SET'}")
        logger.info(f"[DEBUG]   - secret_access_key: {'SET' if secret_access_key else 'NOT SET'}")
        logger.info(f"[DEBUG]   - bucket_name: {bucket_name}")
        logger.info(f"[DEBUG]   - endpoint_url: {endpoint_url if endpoint_url else '(auto-generated)'}")
        logger.info(f"[DEBUG]   - public_url: {public_url if public_url else '(not set)'}")

        if not all([account_id, access_key_id, secret_access_key]):
            logger.error("R2 credentials not configured. Falling back to local storage.")
            logger.error(f"[DEBUG] Missing credentials: account_id={bool(account_id)}, access_key={bool(access_key_id)}, secret={bool(secret_access_key)}")
            local_path = os.getenv("STORAGE_LOCAL_PATH", default_local_path)
            logger.info(f"[DEBUG] Using LocalStorage fallback at {local_path}")
            return LocalStorage(local_path)

        try:
            logger.info(f"[DEBUG] Initializing CloudflareR2Storage with bucket '{bucket_name}'")
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
            logger.error(f"[DEBUG] R2 initialization error: {type(e).__name__}: {str(e)}")
            local_path = os.getenv("STORAGE_LOCAL_PATH", default_local_path)
            logger.info(f"[DEBUG] Using LocalStorage fallback at {local_path}")
            return LocalStorage(local_path)

    # Default to local storage
    local_path = os.getenv("STORAGE_LOCAL_PATH", default_local_path)
    logger.info(f"[DEBUG] Using LocalStorage (default) at {local_path}")
    logger.info(f"[DEBUG] CWD when initializing storage: {Path.cwd()}")
    resolved = Path(local_path).resolve()
    logger.info(f"[DEBUG] Resolved absolute path would be: {resolved}")
    logger.info(f"[DEBUG] Volume mount check — does {resolved} exist? {resolved.exists()}")
    return LocalStorage(local_path)
