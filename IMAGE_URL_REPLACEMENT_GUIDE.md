# Image Hosting & URL Replacement Guide

## Quick Start

### Step 1: Start the Image Server
```bash
python image_server.py
```

You should see:
```
============================================================
🖼️  IMAGE SERVER STARTED
============================================================
✅ Server running at: http://localhost:8889
📁 Serving images from: d:\HRM-Utilities\cogs\images

📋 Available images:
   • http://localhost:8889/footer_icon.webp
   • http://localhost:8889/bottom_banner.png
   ...
```

### Step 2: Add Your Images to the Folder
Place your images in: `d:\HRM-Utilities\cogs\images\`

Expected image files:
- `footer_icon.webp` - Main emoji icon (240x240)
- `footer_icon_say.png` - Say cog icon
- `bottom_banner.png` - Bottom divider banner
- `applications_banner.png` - Applications banner (2576x862)
- `callsigns_banner.png` - Callsigns banner (2576x862)
- `about_us_banner.png` - About Us banner
- `regulations_banner.png` - Regulations banner (2576x862)
- `training_pass_template.png` - Training pass template
- `training_fail_template.png` - Training fail template
- `suggestion_thumbnail.png` - Suggestion thumbnail

### Step 3: Replace URLs in Your Cog
```bash
python replace_image_urls.py about_us 8889
```

Output:
```
============================================================
🔄 IMAGE URL REPLACER
============================================================
📌 Port: 8889
📌 Make sure image_server.py is running on port 8889

📝 Processing: d:\HRM-Utilities\cogs\about_us.py
   ✓ Replaced 1 instance(s) of ABOUT_US.png
   ✓ Replaced 1 instance(s) of bottom.png

✅ Successfully updated d:\HRM-Utilities\cogs\about_us.py
   2 URL(s) replaced

============================================================
✅ Done! Your cog is now using local image URLs.
   Access images at: http://localhost:8889/
============================================================
```

### Step 4: Verify
Check the cog file to see URLs changed:
```python
# Before:
embed.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409314341374656582/ABOUT_US.png?ex=68acedc2&is=68ab9c42&hm=71c262ec46a70395b61bfdf9a44bd51a29058e3399626e021d97a5da4d742721&")

# After:
embed.set_image(url="http://localhost:8889/about_us_banner.png")
```

---

## How It Works

### image_server.py
- Simple HTTP server serving files from `cogs/images/`
- Runs on `http://localhost:8889` by default
- No external dependencies (uses Python stdlib)
- Handles file access safely (no directory traversal)
- Lists available images when accessed directly

### replace_image_urls.py
- Scans a cog file for Discord CDN URLs
- Replaces them with local server URLs
- Handles URL variations with query parameters
- Creates backup by reading/writing safely
- Reports statistics on replacements made

---

## Example Commands

Replace URLs in single cog:
```bash
python replace_image_urls.py about_us
```

Replace URLs with custom port:
```bash
python replace_image_urls.py about_us 9000
```

---

## Troubleshooting

### Images not loading?
1. ✓ Verify `image_server.py` is running
2. ✓ Check images exist in `cogs/images/` folder
3. ✓ Try accessing `http://localhost:8889/` in browser
4. ✓ Check file names match exactly

### URLs not being replaced?
1. ✓ Make sure image files exist in `cogs/images/`
2. ✓ Check the cog file has Discord URLs to replace
3. ✓ Verify file naming matches replacement map

### "Port already in use"?
- Change port: `python image_server.py` → modify script or use different port
- Or kill existing process on that port

---

## File Structure Expected

```
d:\HRM-Utilities\
├── image_server.py          ← Run this first
├── replace_image_urls.py    ← Then run this
├── cogs/
│   ├── about_us.py          ← Cog to update
│   ├── images/              ← Images folder
│   │   ├── footer_icon.webp
│   │   ├── about_us_banner.png
│   │   ├── bottom_banner.png
│   │   └── ... (other images)
```

---

## Manual URL Replacement

If you prefer to do it manually, replace these Discord URLs:

| Discord URL | Local URL |
|------------|-----------|
| `emojis/1409463907294384169.webp` | `http://localhost:8889/footer_icon.webp` |
| `attachments/.../bottom.png` | `http://localhost:8889/bottom_banner.png` |
| `attachments/.../ABOUT_US.png` | `http://localhost:8889/about_us_banner.png` |
| `attachments/.../APPLICATIONS.png` | `http://localhost:8889/applications_banner.png` |
| `attachments/.../CALLSIGNS.png` | `http://localhost:8889/callsigns_banner.png` |
| `attachments/.../REGULATIONS.png` | `http://localhost:8889/regulations_banner.png` |

---

## Why This Approach?

✓ **No Discord dependency** - Images won't expire if Discord takes them down
✓ **Fast loading** - Local server is faster than CDN
✓ **Easy backup** - All images stored locally
✓ **Simple to update** - Just replace files in `images/` folder
✓ **Portable** - Take images with your bot anywhere

---

## Next Steps

1. Ensure `image_server.py` is running while bot uses local URLs
2. Or integrate image serving into your main bot.py
3. Update all other cogs with same process
