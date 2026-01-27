#!/usr/bin/env python3
"""
Image Directory Status - Shows what images exist and what's missing
Run: python image_status.py
"""

import os
from pathlib import Path

# All expected images and their details
EXPECTED_IMAGES = {
    "footer_icon.webp": {
        "used_in": "callsign.py, applications.py, about_us.py, Rules.py, ticket_system.py",
        "size": "240x240",
        "type": "Emoji Icon",
    },
    "footer_icon_say.png": {
        "used_in": "say.py",
        "size": "Variable",
        "type": "Server Icon",
    },
    "bottom_banner.png": {
        "used_in": "trainings.py, callsign.py, applications.py, about_us.py, Rules.py",
        "size": "Wide Banner",
        "type": "Divider",
    },
    "applications_banner.png": {
        "used_in": "applications.py",
        "size": "2576x862",
        "type": "Main Banner",
    },
    "callsigns_banner.png": {
        "used_in": "callsign.py",
        "size": "2576x862",
        "type": "Main Banner",
    },
    "about_us_banner.png": {
        "used_in": "about_us.py",
        "size": "Variable",
        "type": "Main Banner",
    },
    "regulations_banner.png": {
        "used_in": "Rules.py",
        "size": "2576x862",
        "type": "Main Banner",
    },
    "training_pass_template.png": {
        "used_in": "trainings.py",
        "size": "Variable",
        "type": "Template",
    },
    "training_fail_template.png": {
        "used_in": "trainings.py",
        "size": "Variable",
        "type": "Template",
    },
    "suggestion_thumbnail.png": {
        "used_in": "suggestion.py",
        "size": "Small",
        "type": "Thumbnail",
    },
    "ticket_banner_1.png": {
        "used_in": "ticket_system.py",
        "size": "Variable",
        "type": "Main Banner",
    },
    "ticket_banner_2.png": {
        "used_in": "ticket_system.py",
        "size": "Variable",
        "type": "Divider",
    },
    "happy_birthday.gif": {
        "used_in": "happy_birthday.py",
        "size": "Variable",
        "type": "GIF/Animation",
    },
}

def get_images_directory():
    """Get the images directory path"""
    return Path(__file__).parent / "cogs" / "images"

def get_file_size(file_path):
    """Get file size in MB"""
    size = os.path.getsize(file_path)
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"

def main():
    images_dir = get_images_directory()
    
    print("\n" + "=" * 100)
    print("📁 IMAGE DIRECTORY STATUS")
    print("=" * 100)
    print(f"📍 Location: {images_dir}\n")
    
    # Get actual files
    actual_files = set()
    if images_dir.exists():
        actual_files = {f.name for f in images_dir.iterdir() if f.is_file()}
    
    # Check status
    status_data = []
    found_count = 0
    missing_count = 0
    
    for image_name in sorted(EXPECTED_IMAGES.keys()):
        info = EXPECTED_IMAGES[image_name]
        exists = image_name in actual_files
        
        if exists:
            file_path = images_dir / image_name
            size = get_file_size(file_path)
            status = "✅ FOUND"
            found_count += 1
        else:
            size = "-"
            status = "❌ MISSING"
            missing_count += 1
        
        status_data.append([
            status,
            image_name,
            info["type"],
            size,
            info["size"],
            info["used_in"]
        ])
    
    # Print table
    headers = ["Status", "Image Name", "Type", "File Size", "Expected Size", "Used In"]
    print(tabulate_manual(status_data, headers))
    
    # Summary
    print("\n" + "=" * 100)
    print("📊 SUMMARY")
    print("=" * 100)
    print(f"✅ Found:   {found_count}/{len(EXPECTED_IMAGES)}")
    print(f"❌ Missing: {missing_count}/{len(EXPECTED_IMAGES)}")
    print(f"📈 Progress: {int(found_count/len(EXPECTED_IMAGES)*100)}%")
    
    # List found images
    if actual_files:
        print(f"\n🖼️  FOUND IMAGES ({len(actual_files)}):")
        for img in sorted(actual_files):
            file_path = images_dir / img
            size = get_file_size(file_path)
            print(f"   ✓ {img:40} ({size})")
    
    # List missing images
    if missing_count > 0:
        print(f"\n⚠️  MISSING IMAGES ({missing_count}):")
        for image_name in sorted(EXPECTED_IMAGES.keys()):
            if image_name not in actual_files:
                info = EXPECTED_IMAGES[image_name]
                print(f"   ✗ {image_name:40} (Type: {info['type']}, Size: {info['size']})")
                print(f"     └─ Used in: {info['used_in']}")
    
    # Extra files (not in expected list)
    extra_files = actual_files - set(EXPECTED_IMAGES.keys())
    if extra_files:
        print(f"\n📌 EXTRA FILES ({len(extra_files)}):")
        for img in sorted(extra_files):
            file_path = images_dir / img
            size = get_file_size(file_path)
            print(f"   • {img:40} ({size})")
    
    print("\n" + "=" * 100)
    print("💡 NEXT STEPS")
    print("=" * 100)
    
    if missing_count == 0:
        print("✅ All images are present! You can:")
        print("   1. Start the image server: python image_server.py")
        print("   2. Replace URLs in cogs: python replace_image_urls.py <cog_name>")
    else:
        print(f"⏳ Download and upload {missing_count} image(s):")
        for image_name in sorted(EXPECTED_IMAGES.keys()):
            if image_name not in actual_files:
                info = EXPECTED_IMAGES[image_name]
                print(f"   • {image_name} (Used in: {info['used_in'].split(',')[0].strip()})")
        print(f"\nThen run: python image_status.py (to check progress)")
    
    print("=" * 100 + "\n")

def tabulate_manual(data, headers):
    """Simple table printer if tabulate not available"""
    col_widths = [len(h) for h in headers]
    
    for row in data:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # Print header
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_line = "|" + "|".join(f" {h:^{w}} " for h, w in zip(headers, col_widths)) + "|"
    
    result = sep + "\n" + header_line + "\n" + sep + "\n"
    
    # Print rows
    for row in data:
        row_line = "|" + "|".join(f" {str(cell):<{w}} " for cell, w in zip(row, col_widths)) + "|"
        result += row_line + "\n"
    
    result += sep
    return result

if __name__ == "__main__":
    main()
