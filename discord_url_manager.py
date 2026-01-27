#!/usr/bin/env python3
"""
Manage Discord CDN URLs for images.
Discord CDN URLs are generated when the bot uploads images to Discord.
Store them here so the image server can display both local and Discord URLs.

Usage:
    python discord_url_manager.py list
    python discord_url_manager.py add <image_name> <discord_url>
    python discord_url_manager.py remove <image_name>
    python discord_url_manager.py clear
"""

import json
from pathlib import Path
import sys

DISCORD_URLS_FILE = Path(__file__).parent / "cogs" / "images" / "discord_urls.json"


def load_urls():
    """Load Discord URLs from file"""
    if DISCORD_URLS_FILE.exists():
        try:
            with open(DISCORD_URLS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_urls(urls):
    """Save Discord URLs to file"""
    DISCORD_URLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DISCORD_URLS_FILE, 'w') as f:
        json.dump(urls, f, indent=2)


def list_urls():
    """List all Discord URLs"""
    urls = load_urls()
    if not urls:
        print("❌ No Discord URLs registered yet.")
        return
    
    print("\n✅ Discord URLs:")
    print("=" * 80)
    for image_name, url in sorted(urls.items()):
        print(f"📷 {image_name}")
        print(f"   {url}\n")
    print("=" * 80)


def add_url(image_name, discord_url):
    """Add a Discord URL for an image"""
    urls = load_urls()
    urls[image_name] = discord_url
    save_urls(urls)
    print(f"✅ Added Discord URL for: {image_name}")
    print(f"   {discord_url}")


def remove_url(image_name):
    """Remove a Discord URL"""
    urls = load_urls()
    if image_name in urls:
        del urls[image_name]
        save_urls(urls)
        print(f"✅ Removed Discord URL for: {image_name}")
    else:
        print(f"❌ Image not found: {image_name}")


def clear_urls():
    """Clear all Discord URLs"""
    if DISCORD_URLS_FILE.exists():
        DISCORD_URLS_FILE.unlink()
        print("✅ All Discord URLs cleared.")
    else:
        print("ℹ️  No Discord URLs to clear.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_urls()
    elif command == "add":
        if len(sys.argv) < 4:
            print("❌ Usage: python discord_url_manager.py add <image_name> <discord_url>")
            return
        add_url(sys.argv[2], sys.argv[3])
    elif command == "remove":
        if len(sys.argv) < 3:
            print("❌ Usage: python discord_url_manager.py remove <image_name>")
            return
        remove_url(sys.argv[2])
    elif command == "clear":
        clear_urls()
    else:
        print(f"❌ Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
