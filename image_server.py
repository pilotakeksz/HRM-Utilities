#!/usr/bin/env python3
"""
Simple Image Server with Base64 export and working copy buttons.

Usage:
  python image_server.py

Features:
- Serves files from `cogs/images/`.
- `/` shows a dynamic UI listing images.
- `/api/images` returns JSON with image metadata and data-URI (base64) for each image.
- UI buttons: Copy Local URL, Copy Discord URL (if registered), Copy Base64 (data URI).
- Select menu for choosing embed method (image, thumbnail, footer icon, author icon).
- Auto-catalog images to Discord when uploaded.

Note: Serving large images as data URIs can be memory-heavy in browsers.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote
import json
import base64
import mimetypes
import sys
import os
import shutil
import asyncio
import threading

# Discord imports (optional - for auto-catalog)
try:
    import discord
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    print("⚠️  discord.py not installed. Auto-catalog feature disabled.")

PORT = 8889
IMAGES_DIR = Path(__file__).parent / "cogs" / "images"
DISCORD_URLS_FILE = IMAGES_DIR / "discord_urls.json"

# Discord bot configuration (read from environment or file)
DISCORD_TOKEN = os.environ.get('DISCORD_BOT_TOKEN', '')
CATALOG_SERVER_ID = int(os.environ.get('CATALOG_SERVER_ID', '1124324366495260753'))
CATALOG_CHANNEL_ID = int(os.environ.get('CATALOG_CHANNEL_ID', '1465844086480310342'))

# Global Discord client for auto-catalog
discord_client = None
catalog_lock = threading.Lock()


def auto_catalog_image(filename: str, file_path: Path) -> str:
    """
    Auto-catalog a single image to Discord
    Returns: Discord URL if successful, None if failed
    """
    if not DISCORD_AVAILABLE or not DISCORD_TOKEN:
        return None
    
    try:
        with catalog_lock:
            # Run async code in a thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_async_catalog_image(filename, file_path))
            loop.close()
            return result
    except Exception as e:
        print(f'⚠️  Auto-catalog failed for {filename}: {e}')
        return None


async def _async_catalog_image(filename: str, file_path: Path) -> str:
    """Async function to upload image to Discord and store URL"""
    try:
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        
        @client.event
        async def on_ready():
            pass
        
        await client.login(DISCORD_TOKEN)
        
        # Get catalog server and channel
        guild = client.get_guild(CATALOG_SERVER_ID)
        if not guild:
            guild = await client.fetch_guild(CATALOG_SERVER_ID)
        
        channel = guild.get_channel(CATALOG_CHANNEL_ID)
        if not channel:
            channel = await guild.fetch_channel(CATALOG_CHANNEL_ID)
        
        # Upload image
        with open(file_path, 'rb') as f:
            msg = await channel.send(file=discord.File(f, filename))
        
        # Extract URL
        if msg.attachments:
            discord_url = msg.attachments[0].url
            
            # Update discord_urls.json
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            discord_map = {}
            if DISCORD_URLS_FILE.exists():
                try:
                    with open(DISCORD_URLS_FILE, 'r') as f:
                        discord_map = json.load(f)
                except:
                    pass
            
            discord_map[filename] = discord_url
            with open(DISCORD_URLS_FILE, 'w') as f:
                json.dump(discord_map, f, indent=2)
            
            print(f'✅ Auto-cataloged {filename} to Discord')
            return discord_url
        
        await client.close()
        return None
        
    except Exception as e:
        print(f'❌ Error auto-cataloging {filename}: {e}')
        try:
            await client.close()
        except:
            pass
        return None


class Handler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_GET(self):
        path = unquote(self.path.split('?', 1)[0]).lstrip('/')

        if path in ('', '/'):
            self.serve_index()
            return

        # Serve embedded particles.js from embed-builder-web for styling
        if path == 'particles.js':
            p = Path(__file__).parent / 'embed-builder-web' / 'particles.js'
            if p.exists():
                try:
                    data = p.read_text(encoding='utf-8')
                    self._set_headers(200, 'application/javascript; charset=utf-8')
                    self.wfile.write(data.encode('utf-8'))
                    return
                except Exception:
                    pass
            self._set_headers(404, 'text/plain')
            self.wfile.write(b'Not found')
            return

        if path == 'api/images':
            self.serve_api_images()
            return

        # Serve static files (images) directly from IMAGES_DIR
        file_path = IMAGES_DIR / path
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(IMAGES_DIR.resolve())):
                self._set_headers(403, 'text/plain')
                self.wfile.write(b'Access denied')
                return
        except Exception:
            self._set_headers(400, 'text/plain')
            self.wfile.write(b'Invalid path')
            return

        if file_path.exists() and file_path.is_file():
            ctype, _ = mimetypes.guess_type(str(file_path))
            ctype = ctype or 'application/octet-stream'
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                self._set_headers(200, ctype)
                self.wfile.write(data)
            except Exception as e:
                self._set_headers(500, 'text/plain')
                self.wfile.write(f'Error reading file: {e}'.encode())
        else:
            self._set_headers(404, 'text/plain')
            self.wfile.write(b'Not found')

    def do_POST(self):
        """Handle file uploads"""
        path = unquote(self.path.split('?', 1)[0]).lstrip('/')
        
        if path == 'api/upload':
            self.handle_upload()
            return
        
        self._set_headers(404, 'application/json')
        self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def handle_upload(self):
        """Handle image file upload"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            content_type = self.headers.get('Content-Type', '')
            
            if content_length > 50 * 1024 * 1024:  # 50MB limit
                self._set_headers(413, 'application/json')
                self.wfile.write(json.dumps({'error': 'File too large'}).encode())
                return
            
            # Parse multipart form data manually
            boundary = None
            if 'boundary=' in content_type:
                boundary = content_type.split('boundary=')[1].split(';')[0].strip()
            
            if not boundary:
                self._set_headers(400, 'application/json')
                self.wfile.write(json.dumps({'error': 'Invalid multipart form'}).encode())
                return
            
            body = self.rfile.read(content_length)
            parts = body.split(f'--{boundary}'.encode())
            
            filename = None
            file_data = None
            
            for part in parts:
                if b'Content-Disposition' in part:
                    # Extract filename from Content-Disposition header
                    if b'filename=' in part:
                        start = part.find(b'filename="') + 10
                        end = part.find(b'"', start)
                        filename = part[start:end].decode('utf-8')
                        
                        # Extract file data (after headers)
                        header_end = part.find(b'\r\n\r\n')
                        if header_end != -1:
                            file_data = part[header_end + 4:-2]  # -2 for trailing CRLF
                            break
            
            if not filename or not file_data:
                self._set_headers(400, 'application/json')
                self.wfile.write(json.dumps({'error': 'No file provided'}).encode())
                return
            
            # Validate file extension
            filename = Path(filename).name
            allowed_ext = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
            if Path(filename).suffix.lower() not in allowed_ext:
                self._set_headers(400, 'application/json')
                self.wfile.write(json.dumps({'error': f'Unsupported file type. Allowed: {allowed_ext}'}).encode())
                return
            
            # Save file
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            file_path = IMAGES_DIR / filename
            
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            print(f'✅ Uploaded: {filename}')
            
            # Auto-catalog to Discord if available
            auto_catalog_result = None
            if DISCORD_AVAILABLE and DISCORD_TOKEN:
                auto_catalog_result = auto_catalog_image(filename, file_path)
            
            # Return success with file info
            self._set_headers(200, 'application/json')
            response = {
                'success': True,
                'filename': filename,
                'path': str(file_path),
                'auto_cataloged': auto_catalog_result is not None
            }
            
            if auto_catalog_result:
                response['discord_url'] = auto_catalog_result
                response['message'] = f'File {filename} uploaded and automatically cataloged to Discord!'
            else:
                response['message'] = f'File {filename} uploaded successfully. Run !catalogimages to add to Discord catalog.'
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f'❌ Upload error: {e}')
            self._set_headers(500, 'application/json')
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def serve_api_images(self):
        resp = []
        if not IMAGES_DIR.exists():
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        # Load discord_urls.json if present - check multiple locations
        discord_map = {}
        discord_file = IMAGES_DIR / 'discord_urls.json'
        
        # Check cogs/images first
        if discord_file.exists():
            try:
                with open(discord_file, 'r', encoding='utf-8') as f:
                    discord_map = json.load(f)
                print(f"📦 Loaded discord_urls.json from {discord_file}")
            except Exception as e:
                print(f"⚠️  Error loading discord_urls.json: {e}")
                discord_map = {}
        else:
            # Check beta_cogs/images as fallback
            beta_discord_file = Path(__file__).parent / 'beta_cogs' / 'images' / 'discord_urls.json'
            if beta_discord_file.exists():
                try:
                    with open(beta_discord_file, 'r', encoding='utf-8') as f:
                        discord_map = json.load(f)
                    print(f"📦 Loaded discord_urls.json from {beta_discord_file}")
                except Exception as e:
                    print(f"⚠️  Error loading from beta_cogs: {e}")
                    discord_map = {}

        for p in sorted([f for f in IMAGES_DIR.iterdir() if f.is_file() and f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}]):
            try:
                b = p.read_bytes()
                mime, _ = mimetypes.guess_type(str(p))
                mime = mime or 'application/octet-stream'
                uri = f'data:{mime};base64,' + base64.b64encode(b).decode('ascii')
                resp.append({
                    'name': p.name,
                    'size': p.stat().st_size,
                    'local_url': f'http://{get_local_ip()}:{PORT}/{p.name}',
                    'discord_url': discord_map.get(p.name),
                    'data_uri': uri
                })
            except Exception:
                # skip files that can't be read
                continue

        body = json.dumps({'images': resp})
        self._set_headers(200, 'application/json; charset=utf-8')
        self.wfile.write(body.encode('utf-8'))

    def serve_index(self):
        # Avoid using str.format on the HTML template because CSS/JS contain
        # curly braces which conflict with format placeholders. Use simple
        # replacement for the {port} token instead.
        html = INDEX_HTML.replace('{port}', str(PORT))
        self._set_headers(200, 'text/html; charset=utf-8')
        self.wfile.write(html.encode('utf-8'))


def get_local_ip():
    # best-effort local IP detection
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


INDEX_HTML = '''<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Image Server — Base64 Export</title>
    <style>
/* Reset and Base Styles */
* {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
}

:root {
        --primary: #7289da;
        --primary-hover: #677bc4;
        --secondary: #2c2f33;
        --secondary-hover: #23272a;
        --tertiary: #99aab5;
        --background: #36393f;
        --background-secondary: #2f3136;
        --background-tertiary: #202225;
        --text-primary: #ffffff;
        --text-secondary: #b9bbbe;
        --text-muted: #72767d;
        --border: #40444b;
        --border-hover: #4f545c;
        --success: #43b581;
        --warning: #faa61a;
        --danger: #f04747;
        --shadow: rgba(0, 0, 0, 0.2);
        --shadow-lg: rgba(0, 0, 0, 0.4);
}

body {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: var(--background);
        color: var(--text-primary);
        line-height: 1.5;
        overflow-x: hidden;
}

/* Page tweaks */
body { padding: 1.5rem; }
.container { max-width: 1200px; margin: 0 auto; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem; }
.card { padding: 1rem; background: var(--background-secondary); border: 1px solid var(--border); border-radius: 10px; }
.thumb { height: 160px; display:flex;align-items:center;justify-content:center;background:var(--background-tertiary);border-radius:8px;overflow:hidden }
.thumb img { max-width:100%; max-height:100%; object-fit:contain }
.meta { margin-top:0.75rem; color:var(--text-secondary); font-size:0.95rem }
.buttons { margin-top:0.75rem; display:flex; gap:0.5rem; flex-wrap:wrap }
.btn-copy { background:var(--primary); color:#fff; border: none; padding:0.5rem 0.75rem; border-radius:6px; cursor:pointer }
.btn-copy.secondary { background:var(--secondary); color:var(--text-primary) }
.toast { position: fixed; right: 1rem; bottom: 1rem; background: rgba(0,0,0,0.75); color: #fff; padding: 0.5rem 0.75rem; border-radius:6px; display:none; z-index:9999 }

    /* compact header */
.header { background: rgba(32,34,37,0.95); backdrop-filter: blur(6px); border-radius:8px; margin-bottom:1rem }
.header-content { display:flex; align-items:center; justify-content:space-between; padding:0.6rem 1rem }
.logo-text { font-weight:700 }

    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="logo"><div class="logo-text">Image Server</div></div>
            <div class="header-actions"><div class="notice">Server: <span id="server-url">loading...</span></div></div>
        </div>
    </div>

    <div class="container">
        <div id="stats" class="notice">Loading images…</div>
        
        <!-- Upload Section -->
        <div style="background: var(--background-secondary); border: 2px dashed var(--border); border-radius: 10px; padding: 1.5rem; margin-bottom: 1rem; text-align: center; cursor: pointer;" id="upload-zone">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">📤</div>
            <div style="font-weight: 600; margin-bottom: 0.25rem;">Upload Images</div>
            <div style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 0.75rem;">Drag & drop or click to select images</div>
            <input type="file" id="file-input" multiple accept=".png,.jpg,.jpeg,.gif,.webp" style="display: none;">
            <div id="upload-status" style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.5rem;"></div>
        </div>
        
        <div style="margin-bottom:1rem;display:flex;gap:0.5rem">
            <input type="text" id="search-input" class="btn-copy" style="background:var(--background-tertiary);color:var(--text-primary);border:1px solid var(--border);flex:1;padding:0.5rem;border-radius:6px" placeholder="🔍 Search images...">
            <select id="embed-method" class="btn-copy" style="background:var(--background-tertiary);color:var(--text-primary);border:1px solid var(--border);padding:0.5rem;border-radius:6px">
                <option value="set_image">Image</option>
                <option value="set_thumbnail">Thumbnail</option>
                <option value="set_footer">Footer Icon</option>
                <option value="set_author">Author Icon</option>
            </select>
        </div>
        <div id="grid" class="grid"></div>
    </div>

    <div id="toast" class="toast"></div>
    <div id="particles-js" style="position:fixed;inset:0;z-index:-1"></div>

    <script>
    function showToast(msg, isError){
        const t = document.getElementById('toast');
        t.textContent = msg;
        t.style.background = isError ? 'rgba(240,72,71,0.9)' : 'rgba(0,0,0,0.75)';
        t.style.display = 'block';
        clearTimeout(window._toastTimer);
        window._toastTimer = setTimeout(()=>{ t.style.display='none' }, 2200);
    }

    // ExecCommand-only copy helper (no navigator.clipboard)
    function copyTextExec(text, successMsg){
        try{
            const ta = document.createElement('textarea');
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            ta.style.top = '0';
            ta.setAttribute('readonly', '');
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            ta.setSelectionRange(0, ta.value.length);
            const ok = document.execCommand('copy');
            document.body.removeChild(ta);
            if (ok) { showToast(successMsg); return true; }
            showToast('Copy failed', true);
            return false;
        }catch(err){ console.error('exec copy failed', err); showToast('Copy failed', true); return false; }
    }

    // Handle file uploads
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const uploadStatus = document.getElementById('upload-status');

    uploadZone.addEventListener('click', () => fileInput.click());

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.style.background = 'var(--background-tertiary)';
        uploadZone.style.borderColor = 'var(--primary)';
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.style.background = 'var(--background-secondary)';
        uploadZone.style.borderColor = 'var(--border)';
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.style.background = 'var(--background-secondary)';
        uploadZone.style.borderColor = 'var(--border)';
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFiles(files);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFiles(e.target.files);
        }
    });

    async function handleFiles(files) {
        const validExtensions = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp']);
        const filesToUpload = [];

        for (let file of files) {
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (validExtensions.has(ext)) {
                filesToUpload.push(file);
            } else {
                showToast(`Skipped: ${file.name} (unsupported format)`, true);
            }
        }

        if (filesToUpload.length === 0) return;

        uploadStatus.textContent = `Uploading ${filesToUpload.length} file(s)...`;
        let successCount = 0;
        let autoCatalogCount = 0;

        for (let file of filesToUpload) {
            try {
                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    successCount++;
                    if (result.auto_cataloged) {
                        autoCatalogCount++;
                        showToast(`✅ ${file.name} auto-cataloged to Discord!`);
                    } else {
                        showToast(`✅ ${file.name} uploaded`);
                    }
                    console.log(`✅ Uploaded: ${file.name}`, result);
                } else {
                    console.error(`❌ Upload failed for ${file.name}:`, result.error);
                    showToast(`Failed: ${file.name}`, true);
                }
            } catch (error) {
                console.error(`❌ Upload error for ${file.name}:`, error);
                showToast(`Error uploading ${file.name}`, true);
            }
        }

        if (successCount > 0) {
            if (autoCatalogCount > 0) {
                uploadStatus.textContent = `✅ ${successCount}/${filesToUpload.length} uploaded, ${autoCatalogCount} auto-cataloged to Discord!`;
            } else {
                uploadStatus.textContent = `✅ Successfully uploaded ${successCount}/${filesToUpload.length} file(s). Run !catalogimages on Discord to add to catalog.`;
            }
            showToast(`✅ ${successCount} image(s) processed!`);
            // Reload images after successful upload
            setTimeout(load, 500);
        }

        fileInput.value = '';
    }

    async function load(){
        try{
            const r = await fetch('/api/images');
            const data = await r.json();
            const serverUrl = data.images.length? data.images[0].local_url.split('/').slice(0,3).join('/') : window.location.origin;
            document.getElementById('server-url').textContent = serverUrl;
            document.getElementById('stats').textContent = `${data.images.length} images found`;

            const grid = document.getElementById('grid');
            grid.innerHTML='';
            data.images.forEach(img=>{
                const card = document.createElement('div'); card.className='card';
                const thumb = document.createElement('div'); thumb.className='thumb';
                const im = document.createElement('img'); im.src = img.local_url; im.alt=img.name;
                thumb.appendChild(im);
                card.appendChild(thumb);

                const meta = document.createElement('div'); meta.className='meta';
                const discordBadge = img.discord_url ? ' <span style="color: var(--success);">✓ Catalogued</span>' : ' <span style="color: var(--text-muted);">✗ Not in Discord</span>';
                meta.innerHTML = `<strong class="embed-title">${img.name}</strong><div style="margin-top:4px">${(img.size/1024).toFixed(1)} KB${discordBadge}</div>`;
                card.appendChild(meta);

                const buttons = document.createElement('div'); buttons.className='buttons';

                // Discord URL button - ALWAYS show, but styled differently if no URL
                const copyDiscord = document.createElement('button'); 
                copyDiscord.textContent='📋 Copy Discord URL'; 
                copyDiscord.className='btn-copy';
                
                if(img.discord_url) {
                    // Has URL - make it prominent
                    copyDiscord.style.background = 'var(--primary)';
                    copyDiscord.style.fontWeight = '600';
                    copyDiscord.style.order = '-1';
                    copyDiscord.onclick = ()=>{ copyTextExec(img.discord_url, 'Discord URL copied'); };
                } else {
                    // No URL yet - muted style with info
                    copyDiscord.style.background = 'var(--text-muted)';
                    copyDiscord.style.opacity = '0.6';
                    copyDiscord.style.cursor = 'not-allowed';
                    copyDiscord.title = 'Run !catalogimages to catalog this image';
                    copyDiscord.onclick = ()=>{ showToast('Image not yet catalogued. Run !catalogimages', true); };
                }
                buttons.appendChild(copyDiscord);

                const copyLocal = document.createElement('button'); 
                copyLocal.textContent='Copy Local URL'; 
                copyLocal.className='btn-copy secondary';
                copyLocal.onclick = ()=>{ copyTextExec(img.local_url, 'Local URL copied'); };
                buttons.appendChild(copyLocal);

                const copyData = document.createElement('button'); 
                copyData.textContent='Copy Python Line'; 
                copyData.className='btn-copy secondary';
                copyData.onclick = ()=>{ 
                    const method = document.getElementById('embed-method').value;
                    let line;
                    switch(method){
                        case 'set_thumbnail':
                            line = `embed.set_thumbnail(url="${img.data_uri}")`;
                            break;
                        case 'set_footer':
                            line = `embed.set_footer(text="", icon_url="${img.data_uri}")`;
                            break;
                        case 'set_author':
                            line = `embed.set_author(name="", icon_url="${img.data_uri}")`;
                            break;
                        case 'set_image':
                        default:
                            line = `embed.set_image(url="${img.data_uri}")`;
                    }
                    copyTextExec(line, 'Python line copied'); 
                };
                buttons.appendChild(copyData);

                card.appendChild(buttons);
                grid.appendChild(card);
            });
        }catch(e){
            document.getElementById('stats').textContent = 'Failed to load images';
            console.error(e);
            showToast('Failed to load images', true);
        }
    }

    window.addEventListener('load', load);

    // Search/filter functionality
    document.getElementById('search-input').addEventListener('input', function(e){
        const query = e.target.value.toLowerCase();
        const cards = document.querySelectorAll('.card');
        cards.forEach(card=>{
            const name = card.querySelector('.meta strong').textContent.toLowerCase();
            card.style.display = name.includes(query) ? 'block' : 'none';
        });
    });

    // Initialize particles background
    (function(){
        var s = document.createElement('script');
        s.src = '/particles.js';
        s.onload = function(){
            if (window.particlesJS) {
                particlesJS('particles-js', {
                    particles: {
                        number: { value: 80, density: { enable: true, value_area: 800 } },
                        color: { value: ["#7289da", "#ffffff", "#99aab5"] },
                        shape: { type: "circle" },
                        opacity: { value: 0.5 },
                        size: { value: 3 },
                        line_linked: { enable: true, distance: 150, color: "#7289da", opacity: 0.1 },
                        move: { enable: true, speed: 1, direction: "none", random: false, straight: false, out_mode: "out", bounce: false }
                    },
                    interactivity: { detect_on: "canvas", events: { onhover: { enable: true, mode: "repulse" }, onclick: { enable: true, mode: "push" }, resize: true } },
                    retina_detect: true
                });
            }
        };
        document.body.appendChild(s);
    })();
    </script>
</body>
</html>
'''


def main():
    if not IMAGES_DIR.exists():
        print(f'Images directory not found at {IMAGES_DIR}. Creating...')
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    httpd = HTTPServer(('0.0.0.0', PORT), Handler)
    ip = get_local_ip()
    print('='*60)
    print('🖼️  IMAGE SERVER (base64-capable)')
    print('='*60)
    print(f'Listening on: http://0.0.0.0:{PORT}  (network: http://{ip}:{PORT})')
    print(f'Serving images from: {IMAGES_DIR}')
    print('Press Ctrl+C to stop')
    print('='*60)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        httpd.server_close()


if __name__ == '__main__':
    main()
