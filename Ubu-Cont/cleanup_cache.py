#!/usr/bin/env python3
"""
Cleanup Script - Remove Python cache files

Run this after making changes to ensure fresh code is loaded.
"""

import os
import shutil
from pathlib import Path


def cleanup_pycache():
    """Remove all __pycache__ directories and .pyc files."""
    root_dir = Path(__file__).parent

    print("Cleaning up Python cache files...")

    # Remove __pycache__ directories
    pycache_dirs = list(root_dir.rglob("__pycache__"))
    for pycache_dir in pycache_dirs:
        print(f"Removing: {pycache_dir}")
        shutil.rmtree(pycache_dir)

    # Remove .pyc files
    pyc_files = list(root_dir.rglob("*.pyc"))
    for pyc_file in pyc_files:
        print(f"Removing: {pyc_file}")
        os.remove(pyc_file)

    print(f"✓ Cleaned up {len(pycache_dirs)} __pycache__ dirs and {len(pyc_files)} .pyc files")


if __name__ == "__main__":
    cleanup_pycache()
