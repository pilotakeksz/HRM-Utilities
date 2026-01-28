"""
Image Catalog API for web integration
Provides endpoints to access the image URL catalog from the web builder
"""

import json
from pathlib import Path
from typing import Dict, Any

IMAGES_DIR = Path(__file__).parent / "beta_cogs" / "images"
DISCORD_URLS_FILE = IMAGES_DIR / "discord_urls.json"


def get_image_catalog() -> Dict[str, str]:
    """
    Get the complete image catalog as a dictionary
    Returns: {filename: discord_url}
    """
    if not DISCORD_URLS_FILE.exists():
        return {}
    
    try:
        with open(DISCORD_URLS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading image catalog: {e}")
        return {}


def get_image_url(filename: str) -> str:
    """
    Get URL for a specific image by filename
    Returns: discord_url or empty string if not found
    """
    catalog = get_image_catalog()
    return catalog.get(filename, "")


def list_catalogued_images() -> list:
    """
    Get list of all catalogued image filenames
    Returns: [filename1, filename2, ...]
    """
    catalog = get_image_catalog()
    return list(catalog.keys())


def catalog_to_json() -> str:
    """
    Get the entire catalog as JSON string
    """
    catalog = get_image_catalog()
    return json.dumps(catalog, indent=2)


if __name__ == "__main__":
    # Test/debug
    print("📦 Image Catalog API")
    print(f"Catalog file: {DISCORD_URLS_FILE}")
    print(f"Exists: {DISCORD_URLS_FILE.exists()}")
    
    catalog = get_image_catalog()
    print(f"\n✅ Total images: {len(catalog)}")
    
    if catalog:
        print("\nImage URLs:")
        for filename, url in list(catalog.items())[:5]:  # Show first 5
            print(f"  {filename}: {url}")
        if len(catalog) > 5:
            print(f"  ... and {len(catalog) - 5} more")
