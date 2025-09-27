import os
import json
from typing import Tuple

VERSION_FILE = os.path.join("data", "version.txt")
VERSION_META_FILE = os.path.join("data", "version_meta.json")

def get_version() -> Tuple[int, str]:
    """
    Get the current version number and formatted version string.
    Returns: (version_number, version_string)
    """
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Read current version
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                version_num = int(f.read().strip())
        except (ValueError, FileNotFoundError):
            version_num = 0
    else:
        version_num = 0
    
    # Increment version
    version_num += 1
    
    # Save new version
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(str(version_num))
    
    # Save metadata
    metadata = {
        "version": version_num,
        "version_string": f"v{version_num}",
        "last_updated": None  # Will be set when bot starts
    }
    
    with open(VERSION_META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    
    return version_num, f"v{version_num}"

def get_current_version() -> Tuple[int, str]:
    """
    Get the current version without incrementing it.
    Returns: (version_number, version_string)
    """
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                version_num = int(f.read().strip())
        except (ValueError, FileNotFoundError):
            version_num = 0
    else:
        version_num = 0
    
    return version_num, f"v{version_num}"
