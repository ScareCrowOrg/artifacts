"""
Tests for viewer_scanner.py

Tests verify:
- Empty / non-existent directory returns empty list
- Valid viewer directory (with index.html) is discovered
- Directory without index.html is ignored
- Non-directory entries are ignored
"""

import os
import pytest

# Add service root to path so imports resolve without install
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from viewer_scanner import scan_viewers


@pytest.mark.asyncio
async def test_empty_directory_returns_empty_list(tmp_path):
    """scan_viewers returns [] when the directory exists but contains no viewers."""
    result = await scan_viewers(str(tmp_path))
    assert result == []


@pytest.mark.asyncio
async def test_nonexistent_directory_returns_empty_list(tmp_path):
    """scan_viewers returns [] when the directory does not exist."""
    missing = str(tmp_path / "does_not_exist")
    result = await scan_viewers(missing)
    assert result == []


@pytest.mark.asyncio
async def test_valid_viewer_is_discovered(tmp_path):
    """A subdirectory with index.html is returned as a viewer."""
    viewer_dir = tmp_path / "dynamic-workspace"
    viewer_dir.mkdir()
    (viewer_dir / "index.html").write_text("<html></html>")

    result = await scan_viewers(str(tmp_path))

    assert len(result) == 1
    assert result[0]["id"] == "dynamic-workspace"
    assert result[0]["path"] == "/artifacts/canonical/viewers/dynamic-workspace"


@pytest.mark.asyncio
async def test_directory_without_index_html_is_ignored(tmp_path):
    """A subdirectory without index.html is not returned."""
    no_index_dir = tmp_path / "empty-viewer"
    no_index_dir.mkdir()

    result = await scan_viewers(str(tmp_path))
    assert result == []


@pytest.mark.asyncio
async def test_non_directory_files_are_ignored(tmp_path):
    """Regular files in the base directory are ignored."""
    (tmp_path / "some_file.txt").write_text("hello")

    result = await scan_viewers(str(tmp_path))
    assert result == []


@pytest.mark.asyncio
async def test_multiple_viewers_sorted_alphabetically(tmp_path):
    """Multiple valid viewers are returned sorted by directory name."""
    for name in ["zebra-viewer", "alpha-viewer", "beta-viewer"]:
        viewer_dir = tmp_path / name
        viewer_dir.mkdir()
        (viewer_dir / "index.html").write_text("<html></html>")

    result = await scan_viewers(str(tmp_path))

    assert len(result) == 3
    assert [v["id"] for v in result] == ["alpha-viewer", "beta-viewer", "zebra-viewer"]


@pytest.mark.asyncio
async def test_mixed_valid_and_invalid_entries(tmp_path):
    """Only directories with index.html are included; others are skipped."""
    # Valid viewer
    valid = tmp_path / "my-viewer"
    valid.mkdir()
    (valid / "index.html").write_text("<html></html>")

    # Directory without index.html
    no_html = tmp_path / "no-html"
    no_html.mkdir()

    # Plain file
    (tmp_path / "README.md").write_text("docs")

    result = await scan_viewers(str(tmp_path))
    assert len(result) == 1
    assert result[0]["id"] == "my-viewer"
