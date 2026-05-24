import os
import json
import subprocess
import datetime
from typing import Tuple, List, Optional

VERSION_FILE = os.path.join("data", "version.txt")
VERSION_META_FILE = os.path.join("data", "version_meta.json")
COGS_TRACKING_FILE = os.path.join("data", "cogs_tracking.json")

def get_version() -> Tuple[int, str, dict]:
    """
    Get the current version number, formatted version string, and additional info.
    Returns: (version_number, version_string, info_dict)
    """
    os.makedirs("data", exist_ok=True)
    
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
    
    commit_hash, commit_message = get_git_info()
    updated_cogs = get_updated_cogs()
    
    # Track cog updates for this version
    track_cog_updates(updated_cogs, version_num)
    
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(str(version_num))
    
    metadata = {
        "version": version_num,
        "version_string": f"v{version_num}",
        "last_updated": datetime.datetime.now().isoformat(),
        "commit_hash": commit_hash,
        "commit_message": commit_message,
        "updated_cogs": updated_cogs
    }
    
    with open(VERSION_META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    
    return version_num, f"v{version_num}", metadata

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

def get_git_info() -> Tuple[Optional[str], Optional[str]]:
    """
    Get git commit hash and message.
    Returns: (commit_hash, commit_message)
    """
    try:
        result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], 
                              capture_output=True, text=True, timeout=5)
        commit_hash = result.stdout.strip() if result.returncode == 0 else None
        
        result = subprocess.run(['git', 'log', '-1', '--pretty=format:%s'], 
                              capture_output=True, text=True, timeout=5)
        commit_message = result.stdout.strip() if result.returncode == 0 else None
        
        return commit_hash, commit_message
    except Exception:
        return None, None

def get_updated_cogs() -> List[str]:
    """
    Get list of cogs that were recently updated.
    Returns: List of cog names that were modified
    """
    try:
        result = subprocess.run(['git', 'diff', '--name-only', 'HEAD~1', 'HEAD'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return []
        
        modified_files = result.stdout.strip().split('\n')
        updated_cogs = []
        
        for file in modified_files:
            if file.startswith('cogs/') and file.endswith('.py'):
                cog_name = file.replace('cogs/', '').replace('.py', '')
                updated_cogs.append(cog_name)
        
        return updated_cogs
    except Exception:
        return []

def track_cog_updates(updated_cogs: List[str], version_num: int):
    """
    Track which cogs were updated in this version.
    """
    os.makedirs("data", exist_ok=True)
    
    tracking_data = {}
    if os.path.exists(COGS_TRACKING_FILE):
        try:
            with open(COGS_TRACKING_FILE, "r", encoding="utf-8") as f:
                tracking_data = json.load(f)
        except Exception:
            tracking_data = {}
    
    tracking_data[str(version_num)] = {
        "cogs": updated_cogs,
        "timestamp": datetime.datetime.now().isoformat(),
        "version": version_num
    }
    
    with open(COGS_TRACKING_FILE, "w", encoding="utf-8") as f:
        json.dump(tracking_data, f, indent=2)

def get_version_info() -> dict:
    """
    Get comprehensive version information including git and cog updates.
    Returns: Dictionary with version, git, and cog information
    """
    version_num, version_string = get_current_version()
    commit_hash, commit_message = get_git_info()
    updated_cogs = get_updated_cogs()
    
    return {
        "version": version_num,
        "version_string": version_string,
        "commit_hash": commit_hash,
        "commit_message": commit_message,
        "updated_cogs": updated_cogs
    }
