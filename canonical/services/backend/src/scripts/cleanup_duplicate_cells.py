#!/usr/bin/env python
"""
Cleanup script for duplicate canonical cell types.

This script identifies and removes duplicate canonical cell type files,
keeping only one instance of each unique cell type based on content.

Usage:
    python scripts/cleanup_duplicate_cells.py [--dry-run]
    
Options:
    --dry-run: Show what would be deleted without actually deleting files
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import SCAREFERA_LAB_DIR


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_cell_content_hash(cell_path: Path) -> str:
    """
    Get a normalized hash of the cell content (excluding id).
    
    Args:
        cell_path: Path to the cell JSON file
        
    Returns:
        JSON string of normalized content
    """
    with open(cell_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Remove id field for content comparison
    data.pop('id', None)
    
    # Return sorted JSON string for consistent comparison
    return json.dumps(data, sort_keys=True)


def find_duplicates(tipos_celula_dir: Path) -> Dict[str, List[Path]]:
    """
    Find duplicate canonical cell files based on content.
    
    Args:
        tipos_celula_dir: Directory containing canonical cell type files
        
    Returns:
        Dictionary mapping content hash to list of file paths with that content
    """
    content_to_files: Dict[str, List[Path]] = defaultdict(list)
    
    for json_file in tipos_celula_dir.glob("*.json"):
        try:
            content_hash = get_cell_content_hash(json_file)
            content_to_files[content_hash].append(json_file)
        except Exception as e:
            logger.error(f"Error processing {json_file}: {e}")
    
    # Only return entries with duplicates
    return {k: v for k, v in content_to_files.items() if len(v) > 1}


def cleanup_duplicates(
    duplicates: Dict[str, List[Path]],
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Clean up duplicate files, keeping only one of each.
    
    Args:
        duplicates: Dictionary of content hash to list of duplicate files
        dry_run: If True, don't actually delete files
        
    Returns:
        Tuple of (files_kept, files_deleted)
    """
    files_kept = 0
    files_deleted = 0
    
    for content_hash, file_list in duplicates.items():
        # Sort by filename to have consistent behavior
        file_list = sorted(file_list, key=lambda p: p.name)
        
        # Keep the first file, delete the rest
        keep_file = file_list[0]
        delete_files = file_list[1:]
        
        logger.info(f"Keeping: {keep_file.name}")
        files_kept += 1
        
        for delete_file in delete_files:
            if dry_run:
                logger.info(f"  [DRY-RUN] Would delete: {delete_file.name}")
            else:
                logger.info(f"  Deleting: {delete_file.name}")
                delete_file.unlink()
            files_deleted += 1
    
    return files_kept, files_deleted


def main():
    """Main cleanup function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Cleanup duplicate canonical cell type files'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    args = parser.parse_args()
    
    # Get path to canonical notebook item types directory
    tipos_celula_dir = SCAREFERA_LAB_DIR / "artifacts" / "canonical" / "notebook_item_types"
    
    if not tipos_celula_dir.exists():
        logger.error(f"Directory not found: {tipos_celula_dir}")
        return 1
    
    logger.info(f"Scanning directory: {tipos_celula_dir}")
    
    # Find all JSON files
    all_files = list(tipos_celula_dir.glob("*.json"))
    logger.info(f"Found {len(all_files)} total canonical cell files")
    
    # Find duplicates
    duplicates = find_duplicates(tipos_celula_dir)
    
    if not duplicates:
        logger.info("No duplicates found!")
        return 0
    
    # Calculate statistics
    total_duplicate_files = sum(len(files) for files in duplicates.values())
    unique_cell_types = len(duplicates)
    
    logger.info(f"\nFound {unique_cell_types} unique cell types with duplicates")
    logger.info(f"Total duplicate files: {total_duplicate_files}")
    
    # Show details about each duplicate group
    for i, (content_hash, file_list) in enumerate(duplicates.items(), 1):
        logger.info(f"\nDuplicate group {i}:")
        # Load one file to show description
        try:
            with open(file_list[0], 'r') as f:
                data = json.load(f)
                logger.info(f"  Description: {data.get('descricao', 'N/A')}")
                logger.info(f"  Duplicates: {len(file_list)} files")
        except Exception as e:
            logger.error(f"  Error reading file: {e}")
    
    # Perform cleanup
    logger.info(f"\n{'=' * 60}")
    if args.dry_run:
        logger.info("DRY RUN MODE - No files will be deleted")
    else:
        logger.info("CLEANUP MODE - Files will be deleted")
    logger.info(f"{'=' * 60}\n")
    
    files_kept, files_deleted = cleanup_duplicates(duplicates, dry_run=args.dry_run)
    
    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("SUMMARY")
    logger.info(f"{'=' * 60}")
    logger.info(f"Files kept: {files_kept}")
    logger.info(f"Files deleted: {files_deleted}")
    
    if args.dry_run:
        logger.info("\nThis was a dry run. Run without --dry-run to actually delete files.")
    else:
        logger.info("\nCleanup completed successfully!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
