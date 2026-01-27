#!/usr/bin/env python3
"""
Image URL Utility Module
Use this to get Discord CDN URLs for images in your cogs

Example usage in a cog:
    from utils.image_urls import get_image_url
    
    @commands.command()
    async def my_command(self, ctx):
        image_url = get_image_url('bottom_banner.png')
        if image_url:
            embed.set_image(url=image_url)
        await ctx.send(embed=embed)
"""

import json
from pathlib import Path

DISCORD_URLS_FILE = Path(__file__).parent.parent / "cogs" / "images" / "discord_urls.json"

def get_image_url(image_filename):
    """
    Get the Discord CDN URL for an image
    
    Args:
        image_filename: Name of the image file (e.g., 'bottom_banner.png')
    
    Returns:
        str: Discord CDN URL if found, None otherwise
    
    Example:
        url = get_image_url('bottom_banner.png')
        if url:
            embed.set_image(url=url)
    """
    if DISCORD_URLS_FILE.exists():
        try:
            with open(DISCORD_URLS_FILE, 'r') as f:
                urls = json.load(f)
                return urls.get(image_filename)
        except Exception as e:
            print(f"⚠️ Error loading image URL: {e}")
    
    return None

def get_all_image_urls():
    """
    Get all registered Discord image URLs
    
    Returns:
        dict: Dictionary of {filename: url}
    """
    if DISCORD_URLS_FILE.exists():
        try:
            with open(DISCORD_URLS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading image URLs: {e}")
    
    return {}

def image_exists(image_filename):
    """Check if an image URL is registered"""
    urls = get_all_image_urls()
    return image_filename in urls

def get_image_url_safe(image_filename, fallback_url=None):
    """
    Get image URL with a fallback if not found
    
    Args:
        image_filename: Name of the image file
        fallback_url: URL to use if image not found (optional)
    
    Returns:
        str: Discord CDN URL or fallback_url or None
    """
    url = get_image_url(image_filename)
    if url:
        return url
    return fallback_url
