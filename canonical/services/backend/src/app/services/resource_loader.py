"""
Resource Loader Service.

Provides unified access to cell type resources regardless of origin (local filesystem or cloud storage).
All resources are staged in a temporary area for consistent execution.

This abstraction layer:
1. Downloads remote files to temporary cache
2. Stages local files to the same temporary structure
3. Provides uniform paths for execution
4. Manages cache lifecycle and cleanup
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ResourceLoader:
    """
    Unified resource loader for cell type artifacts.

    Handles both local (Git/filesystem) and remote (Cloud Storage) resources,
    staging them in a temporary area for consistent execution.
    """

    def __init__(
        self,
        cache_base_path: str = "/tmp/scareverse/cell_resources",
        cache_ttl_seconds: int = 3600,  # 1 hour default
    ):
        """
        Initialize the resource loader.

        Args:
            cache_base_path: Base path for temporary resource cache
            cache_ttl_seconds: Time-to-live for cached resources
        """
        self.cache_base_path = Path(cache_base_path)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache_base_path.mkdir(parents=True, exist_ok=True)
        logger.info("ResourceLoader initialized with cache at %s", self.cache_base_path)

    def stage_resource(
        self, resource_uri: str, target_subdir: str, resource_type: str = "local"
    ) -> Path:
        """
        Stage a resource to the temporary cache area.

        Args:
            resource_uri: URI of the resource (file path or gs://... URL)
            target_subdir: Subdirectory in cache (e.g., 'example/backend/scripts')
            resource_type: 'local' or 'remote'

        Returns:
            Path to the staged resource

        Example:
            >>> loader = ResourceLoader()
            >>> staged = loader.stage_resource(
            ...     "artifacts/canonical/cell_types/example/backend/scripts/main.py",
            ...     "example/backend/scripts",
            ...     "local"
            ... )
            >>> print(staged)
            /tmp/scareverse/cell_resources/example/backend/scripts/main.py
        """
        # Create target directory
        target_dir = self.cache_base_path / target_subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        # Extract filename from URI
        filename = Path(resource_uri).name
        target_path = target_dir / filename

        # Stage based on resource type
        if resource_type == "local":
            target_path = self._stage_local_resource(resource_uri, target_path)
        elif resource_type == "remote":
            target_path = self._stage_remote_resource(resource_uri, target_path)
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")

        logger.debug("Staged resource %s -> %s", resource_uri, target_path)
        return target_path

    def _stage_local_resource(self, source_path: str, target_path: Path) -> Path:
        """
        Stage a local filesystem resource.

        Creates a symlink or copy to the cache area.

        Args:
            source_path: Path to local file
            target_path: Target path in cache

        Returns:
            Path to staged resource
        """
        source = Path(source_path)

        if not source.exists():
            raise FileNotFoundError(f"Local resource not found: {source_path}")

        # Use symlink for local files to save space
        if target_path.exists() or target_path.is_symlink():
            target_path.unlink()

        try:
            # Try symlink first (faster, saves space)
            target_path.symlink_to(source.resolve())
        except OSError:
            # Fallback to copy if symlink not supported
            shutil.copy2(source, target_path)

        return target_path

    def _stage_remote_resource(self, remote_uri: str, target_path: Path) -> Path:
        """
        Stage a remote cloud storage resource.

        Downloads the file to cache if not present or expired.

        Args:
            remote_uri: Cloud storage URI (gs://bucket/path or s3://bucket/path)
            target_path: Target path in cache

        Returns:
            Path to staged resource
        """
        # Check if cached and fresh
        if self._is_cache_fresh(target_path):
            logger.debug("Using cached remote resource: %s", target_path)
            return target_path

        # Download based on URI scheme
        if remote_uri.startswith("gs://"):
            self._download_from_gcs(remote_uri, target_path)
        elif remote_uri.startswith("s3://"):
            self._download_from_s3(remote_uri, target_path)
        else:
            raise ValueError(f"Unsupported remote URI scheme: {remote_uri}")

        # Update cache metadata
        self._update_cache_metadata(target_path)

        return target_path

    def _is_cache_fresh(self, cached_path: Path) -> bool:
        """
        Check if a cached file is still fresh (within TTL).

        Args:
            cached_path: Path to cached file

        Returns:
            True if cache is fresh, False otherwise
        """
        if not cached_path.exists():
            return False

        # Check file modification time
        mtime = datetime.fromtimestamp(cached_path.stat().st_mtime)
        age = datetime.now() - mtime

        return age.total_seconds() < self.cache_ttl_seconds

    def _update_cache_metadata(self, cached_path: Path):
        """
        Update cache metadata for a file.

        Currently just updates modification time. Could be extended
        to store additional metadata in a sidecar file.

        Args:
            cached_path: Path to cached file
        """
        cached_path.touch()

    def _download_from_gcs(self, gcs_uri: str, target_path: Path):
        """
        Download file from Google Cloud Storage.

        Args:
            gcs_uri: GCS URI (gs://bucket/path)
            target_path: Target path for download
        """
        # TODO: Implement in Phase 3
        # For now, raise NotImplementedError
        raise NotImplementedError(
            "GCS download will be implemented in Phase 3. "
            f"Attempted to download: {gcs_uri}"
        )

    def _download_from_s3(self, s3_uri: str, target_path: Path):
        """
        Download file from AWS S3.

        Args:
            s3_uri: S3 URI (s3://bucket/path)
            target_path: Target path for download
        """
        # TODO: Implement in Phase 3
        # For now, raise NotImplementedError
        raise NotImplementedError(
            "S3 download will be implemented in Phase 3. "
            f"Attempted to download: {s3_uri}"
        )

    def stage_cell_type(
        self,
        cell_type_id: str,
        refs: Dict[str, List[str]],
        base_local_path: Optional[Path] = None,
    ) -> Dict[str, List[Path]]:
        """
        Stage all resources for a cell type.

        Args:
            cell_type_id: ID of the cell type
            refs: Dict mapping ref types to URIs
            base_local_path: Base path for local files (if applicable)

        Returns:
            Dict mapping ref types to staged paths

        Example:
            >>> loader = ResourceLoader()
            >>> refs = {
            ...     "scripts": ["backend/scripts/main.py"],
            ...     "view": ["frontend/View.vue"]
            ... }
            >>> staged = loader.stage_cell_type("example", refs, Path("artifacts/canonical/cell_types/example"))
        """
        staged_refs = {}

        for ref_type, resource_uris in refs.items():
            staged_paths = []

            for uri in resource_uris:
                # Determine if local or remote
                if uri.startswith("gs://") or uri.startswith("s3://"):
                    resource_type = "remote"
                    full_uri = uri
                else:
                    resource_type = "local"
                    # Resolve local path
                    if base_local_path:
                        full_uri = str(base_local_path / uri)
                    else:
                        full_uri = uri

                # Determine target subdirectory
                # Extract relative path from URI for directory structure
                if resource_type == "remote":
                    # For remote, use cell_type_id + ref_type
                    target_subdir = f"{cell_type_id}/{ref_type}"
                else:
                    # For local, preserve directory structure
                    rel_dir = Path(uri).parent
                    target_subdir = f"{cell_type_id}/{rel_dir}"

                # Stage the resource
                try:
                    staged_path = self.stage_resource(
                        full_uri, target_subdir, resource_type
                    )
                    staged_paths.append(staged_path)
                except Exception as e:
                    logger.error("Failed to stage resource %s: %s", uri, e)
                    raise

            staged_refs[ref_type] = staged_paths

        return staged_refs

    def cleanup_old_cache(self, max_age_seconds: Optional[int] = None):
        """
        Clean up old cached files.

        Args:
            max_age_seconds: Maximum age in seconds (defaults to cache_ttl_seconds)
        """
        if max_age_seconds is None:
            max_age_seconds = self.cache_ttl_seconds

        cutoff_time = datetime.now() - timedelta(seconds=max_age_seconds)
        cleaned_count = 0

        for root, dirs, files in os.walk(self.cache_base_path):
            for filename in files:
                filepath = Path(root) / filename
                mtime = datetime.fromtimestamp(filepath.stat().st_mtime)

                if mtime < cutoff_time:
                    try:
                        filepath.unlink()
                        cleaned_count += 1
                        logger.debug("Cleaned old cache file: %s", filepath)
                    except Exception as e:
                        logger.warning("Failed to clean cache file %s: %s", filepath, e)

        logger.info("Cleaned %s old cache files", cleaned_count)

    def clear_cache(self, cell_type_id: Optional[str] = None):
        """
        Clear cache for a specific cell type or all cache.

        Args:
            cell_type_id: If provided, clear only this cell type's cache
        """
        if cell_type_id:
            cache_dir = self.cache_base_path / cell_type_id
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                logger.info("Cleared cache for cell type: %s", cell_type_id)
        else:
            if self.cache_base_path.exists():
                shutil.rmtree(self.cache_base_path)
                self.cache_base_path.mkdir(parents=True, exist_ok=True)
                logger.info("Cleared all resource cache")


# Global instance
_resource_loader: Optional[ResourceLoader] = None


def get_resource_loader() -> ResourceLoader:
    """
    Get the global resource loader instance.

    Returns:
        Global ResourceLoader instance
    """
    global _resource_loader
    if _resource_loader is None:
        _resource_loader = ResourceLoader()
    return _resource_loader
