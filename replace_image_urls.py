#!/usr/bin/env python3
"""
Replace Discord image URLs with local image URLs
Usage: python replace_image_urls.py <cog_name> [port]
Example: python replace_image_urls.py about_us 8889
"""

import os
import sys
import re
from pathlib import Path

# URL replacement mapping
URL_REPLACEMENTS = {
    # Footer icons
    "https://cdn.discordapp.com/emojis/1409463907294384169.webp?size=240": "http://localhost:PORT/footer_icon.webp",
    "https://images-ext-1.discordapp.net/external/_d7d0RmGwlFEwwKlYDfachyeC_skH7txYK5GzDan4ZI/https/cdn.discordapp.com/icons/1329908357812981882/fa763c9516fc5a9982b48c69c0a18e18.png": "http://localhost:PORT/footer_icon_say.png",
    
    # Bottom banner (multiple variants)
    "https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png": "http://localhost:PORT/bottom_banner.png",
    
    # Banners
    "https://media.discordapp.net/attachments/1409252771978280973/1409314341764861993/APPLICATIONS.png": "http://localhost:PORT/applications_banner.png",
    "https://media.discordapp.net/attachments/1409252771978280973/1409314343178207322/CALLSIGNS.png": "http://localhost:PORT/callsigns_banner.png",
    "https://cdn.discordapp.com/attachments/1409252771978280973/1409314341374656582/ABOUT_US.png": "http://localhost:PORT/about_us_banner.png",
    "https://media.discordapp.net/attachments/1409252771978280973/1409314376019738664/REGULATIONS.png": "http://localhost:PORT/regulations_banner.png",
    
    # Templates
    "https://cdn.discordapp.com/attachments/1409252771978280973/1439393464394580008/Template.png": "http://localhost:PORT/training_pass_template.png",
    "https://media.discordapp.net/attachments/1409252771978280973/1439393779722485942/Template.png": "http://localhost:PORT/training_fail_template.png",
    
    # Thumbnail
    "https://cdn.discordapp.com/attachments/1376647403712675991/1376652854391083269/image-141.png": "http://localhost:PORT/suggestion_thumbnail.png",
}

def replace_urls_in_file(file_path, port=8889):
    """Replace Discord URLs with local image server URLs"""
    
    print(f"\n📝 Processing: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False
    
    original_content = content
    replacements_made = 0
    
    # Replace each URL
    for old_url, new_url_template in URL_REPLACEMENTS.items():
        new_url = new_url_template.replace("PORT", str(port))
        
        # Find all variations of the URL (with and without query parameters)
        # This handles the ?ex=...&is=...&hm=... parameters that Discord adds
        pattern = re.escape(old_url) + r'(\?[^"\']*)?'
        matches = re.findall(pattern, content)
        
        if matches:
            # Replace with exact URL match
            content = re.sub(pattern, new_url, content)
            print(f"   ✓ Replaced {len(matches)} instance(s) of {old_url.split('/')[-1]}")
            replacements_made += len(matches)
    
    # Write back if changes were made
    if content != original_content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\n✅ Successfully updated {file_path}")
            print(f"   {replacements_made} URL(s) replaced")
            return True
        except Exception as e:
            print(f"❌ Error writing file: {e}")
            return False
    else:
        print(f"   ℹ️  No Discord image URLs found to replace")
        return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python replace_image_urls.py <cog_name> [port]")
        print("Example: python replace_image_urls.py about_us 8889")
        print()
        print("Available cogs with image URLs:")
        cogs_dir = Path(__file__).parent / "cogs"
        for cog_file in sorted(cogs_dir.glob("*.py")):
            print(f"  • {cog_file.stem}")
        sys.exit(1)
    
    cog_name = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8889
    
    # Build file path
    cog_file = Path(__file__).parent / "cogs" / f"{cog_name}.py"
    
    if not cog_file.exists():
        print(f"❌ Error: Cog file not found: {cog_file}")
        sys.exit(1)
    
    print("=" * 60)
    print("🔄 IMAGE URL REPLACER")
    print("=" * 60)
    print(f"📌 Port: {port}")
    print(f"📌 Make sure image_server.py is running on port {port}")
    
    if replace_urls_in_file(cog_file, port):
        print("\n" + "=" * 60)
        print("✅ Done! Your cog is now using local image URLs.")
        print(f"   Access images at: http://localhost:{port}/")
        print("=" * 60)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
