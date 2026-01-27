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
- Clipboard actions use `navigator.clipboard.writeText` with a robust fallback modal when needed.

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

PORT = 8889
IMAGES_DIR = Path(__file__).parent / "cogs" / "images"


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

    def serve_api_images(self):
        resp = []
        if not IMAGES_DIR.exists():
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        # Load discord_urls.json if present
        discord_map = {}
        discord_file = IMAGES_DIR / 'discord_urls.json'
        if discord_file.exists():
            try:
                with open(discord_file, 'r', encoding='utf-8') as f:
                    discord_map = json.load(f)
            except Exception:
                discord_map = {}

        for p in sorted([f for f in IMAGES_DIR.iterdir() if f.is_file()]):
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
    body{font-family:Arial,Helvetica,sans-serif;background:#f6f7fb;margin:0;padding:20px}
    .container{max-width:1100px;margin:0 auto}
    header{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
    h1{font-size:20px;margin:0}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
    .card{background:#fff;border-radius:8px;padding:12px;border:1px solid #e6e9ef}
    .thumb{height:140px;background:#fafafa;border-radius:6px;display:flex;align-items:center;justify-content:center;overflow:hidden}
    .thumb img{max-width:100%;max-height:100%}
    .meta{margin-top:8px;font-size:13px;color:#333}
    .buttons{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap}
    button{padding:8px 10px;border-radius:6px;border:0;background:#4b6cff;color:white;cursor:pointer}
    button.secondary{background:#6c757d}
    .small{font-size:12px;padding:6px 8px}
    .notice{color:#666;font-size:13px}
    /* modal */
    .modal{position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,0.5)}
    .modal .box{background:white;padding:16px;border-radius:8px;max-width:90%;max-height:80%;overflow:auto}
    textarea{width:100%;height:220px}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Image Server — Base64 Export</h1>
      <div class="notice">Server: <span id="server-url">loading...</span></div>
    </header>
    <div id="stats" class="notice">Loading images…</div>
    <div id="grid" class="grid"></div>
  </div>

  <div id="modal" class="modal"><div class="box"><h3>Copy</h3><p>Use Ctrl/Cmd+C to copy the selected text.</p><textarea id="modal-text"></textarea><p style="text-align:right;margin-top:8px"><button id="modal-close">Close</button></p></div></div>

  <script>
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
        meta.innerHTML = `<strong>${img.name}</strong><br>${(img.size/1024).toFixed(1)} KB`;
        card.appendChild(meta);

        const buttons = document.createElement('div'); buttons.className='buttons';

        const copyLocal = document.createElement('button'); copyLocal.textContent='Copy Local URL'; copyLocal.className='small';
        copyLocal.onclick = ()=>copyText(img.local_url);
        buttons.appendChild(copyLocal);

        if(img.discord_url){
          const copyDiscord = document.createElement('button'); copyDiscord.textContent='Copy Discord URL'; copyDiscord.className='small secondary';
          copyDiscord.onclick = ()=>copyText(img.discord_url);
          buttons.appendChild(copyDiscord);
        }

        const copyData = document.createElement('button'); copyData.textContent='Copy Base64 (data URI)'; copyData.className='small';
        copyData.onclick = ()=>copyDataUri(img.data_uri);
        buttons.appendChild(copyData);

        card.appendChild(buttons);
        grid.appendChild(card);
      });
    }catch(e){
      document.getElementById('stats').textContent = 'Failed to load images';
      console.error(e);
    }
  }

  async function copyText(text){
    try{
      await navigator.clipboard.writeText(text);
      alert('Copied to clipboard');
    }catch(e){
      // fallback modal
      showModal(text);
    }
  }

  async function copyDataUri(dataUri){
    try{
      await navigator.clipboard.writeText(dataUri);
      alert('Base64 data URI copied to clipboard');
    }catch(e){
      // fallback: show modal with selected text
      showModal(dataUri);
    }
  }

  function showModal(text){
    const modal = document.getElementById('modal');
    const ta = document.getElementById('modal-text');
    ta.value = text;
    modal.style.display='flex';
    ta.select();
  }
  document.getElementById('modal-close').onclick = ()=>{ document.getElementById('modal').style.display='none'; };

  window.addEventListener('load', load);
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
#!/usr/bin/env python3
"""
Simple HTTP server to serve images from cogs/images folder
Run: python image_server.py
Then replace Discord URLs with: http://localhost:8889/image_name.ext
"""

import os
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote
import json

class ImageHandler(SimpleHTTPRequestHandler):
    """Custom handler to serve images from cogs/images"""
    
    # Set the image directory
    IMAGES_DIR = Path(__file__).parent / "cogs" / "images"
    
    def do_GET(self):
        """Handle GET requests for images"""
        # Remove leading slash and decode URL
        path = unquote(self.path)
        
        # Handle query parameters
        if '?' in path:
            path = path.split('?')[0]
        
        path = path.lstrip('/')
        
        # API endpoint for server info
        if path == 'api/info':
            self.serve_api_info()
            return
        
        # Root path - show directory listing
        if path == '' or path == '/':
            self.serve_directory_listing()
            return
        
        # Security: prevent directory traversal
        if '..' in path:
            self.send_error(400, "Invalid path")
            return
        
        # Build full file path
        file_path = self.IMAGES_DIR / path
        
        # Verify file exists and is in images directory
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(self.IMAGES_DIR.resolve())):
                self.send_error(403, "Access denied")
                return
        except Exception as e:
            self.send_error(400, f"Invalid path: {e}")
            return
        
        # Serve the file
        if file_path.exists() and file_path.is_file():
            # Determine content type
            content_type = self.guess_type(file_path)
            
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                self.send_response(200)
                self.send_header('Content-type', content_type)
                self.send_header('Content-Length', len(content))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Error reading file: {e}")
        else:
            self.send_error(404, "Image not found")
    
    def serve_api_info(self):
        """Serve JSON API with server info and file list"""
        try:
            files = sorted([f for f in self.IMAGES_DIR.iterdir() if f.is_file()])
            server_ip = get_local_ip()
            
            # Read Discord URLs from file if it exists
            discord_urls = {}
            discord_urls_file = self.IMAGES_DIR / "discord_urls.json"
            if discord_urls_file.exists():
                try:
                    with open(discord_urls_file, 'r') as f:
                        discord_urls = json.load(f)
                except:
                    pass
            
            data = {
                "server_ip": server_ip,
                "port": 8889,
                "server_url": f"http://{server_ip}:8889",
                "images": [
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "local_url": f"http://{server_ip}:8889/{f.name}",
                        "discord_url": discord_urls.get(f.name, None)
                    }
                    for f in files
                ]
            }
            
            response = json.dumps(data)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', len(response.encode()))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error: {e}")
    
    def serve_directory_listing(self):
        """Serve HTML directory listing with image previews (loaded dynamically via API)"""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Server - HRM Utilities</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }
        .header h1 {
            font-size: 32px;
            margin-bottom: 10px;
        }
        .header p {
            font-size: 16px;
            opacity: 0.9;
        }
        .content {
            padding: 40px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
            background: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
        }
        .stat-item {
            text-align: center;
        }
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
            word-break: break-all;
            line-height: 1.2;
        }
        .stat-label {
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }
        .images-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
        }
        .image-card {
            background: #f9f9f9;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            overflow: hidden;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
        }
        .image-card:hover {
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            transform: translateY(-5px);
            border-color: #667eea;
        }
        .image-preview {
            width: 100%;
            height: 200px;
            background: #f0f0f0;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        .image-preview img {
            max-width: 100%;
            max-height: 100%;
            object-fit: cover;
        }
        .image-info {
            padding: 15px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
        }
        .image-name {
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
            font-size: 14px;
            word-break: break-word;
        }
        .image-url {
            background: #f0f0f0;
            padding: 8px;
            border-radius: 4px;
            font-size: 12px;
            font-family: monospace;
            color: #667eea;
            margin-bottom: 10px;
            overflow: hidden;
            word-break: break-all;
            white-space: normal;
            transition: background 0.2s;
            line-height: 1.4;
            max-height: 60px;
            overflow-y: auto;
            cursor: text;
        }
        .image-url:hover {
            background: #e0e0e0;
        }
        .url-label {
            font-size: 11px;
            color: #999;
            margin-bottom: 3px;
            font-weight: bold;
        }
        .url-row {
            margin-bottom: 10px;
        }
        .image-size {
            font-size: 12px;
            color: #999;
            margin-bottom: 10px;
        }
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: #999;
        }
        .empty-state h2 {
            margin-bottom: 10px;
            color: #666;
        }
        .footer {
            background: #f5f5f5;
            padding: 20px;
            text-align: center;
            color: #999;
            font-size: 12px;
            border-top: 1px solid #e0e0e0;
        }
        .copy-btn {
            padding: 8px 12px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: background 0.2s;
            font-weight: bold;
        }
        .copy-btn:hover {
            background: #764ba2;
        }
        .copy-feedback {
            display: none;
            color: #4caf50;
            font-size: 12px;
            margin-top: 5px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖼️ Image Server</h1>
            <p>HRM Utilities - Local Image Hosting</p>
        </div>
        
        <div class="content">
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-number" id="image-count">0</div>
                    <div class="stat-label">Images Available</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="total-size">0 MB</div>
                    <div class="stat-label">Total Size</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="server-url" style="font-size: 18px;">Loading...</div>
                    <div class="stat-label">Server URL (for embeds)</div>
                </div>
            </div>
            
            <div id="images-container"></div>
        </div>
        
        <div class="footer">
            <p>✨ Place images in <strong>cogs/images/</strong> folder and refresh this page</p>
            <p style="margin-top: 10px;">💡 Click URLs or "Copy URL" button to copy to clipboard</p>
        </div>
    </div>
    
    <script>
        // Fetch server info and images dynamically
        async function loadImages() {
            try {
                const response = await fetch('/api/info');
                const data = await response.json();
                
                // Update server URL
                const serverUrl = data.server_url;
                document.getElementById('server-url').textContent = serverUrl;
                
                // Update stats
                document.getElementById('image-count').textContent = data.images.length;
                
                const totalSize = data.images.reduce((sum, img) => sum + img.size, 0);
                document.getElementById('total-size').textContent = formatSize(totalSize);
                
                // Build grid
                const container = document.getElementById('images-container');
                
                if (data.images.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <h2>📭 No Images Found</h2>
                            <p>Add images to: cogs/images/</p>
                        </div>
                    `;
                    return;
                }
                
                container.innerHTML = '<div class="images-grid" id="images-grid"></div>';
                const grid = document.getElementById('images-grid');
                
                data.images.forEach(img => {
                    const card = document.createElement('div');
                    card.className = 'image-card';
                    
                    const safeId = img.name.replace(/[^a-z0-9]/gi, '_');
                    const localFeedbackId = 'local_feedback_' + safeId;
                    const discordFeedbackId = 'discord_feedback_' + safeId;
                    
                    let discordUrlHtml = '';
                    if (img.discord_url) {
                        discordUrlHtml = `
                            <div class="url-row">
                                <div class="url-label">Discord URL:</div>
                                <div class="image-url" data-url="${img.discord_url}">
                                    ${img.discord_url}
                                </div>
                                <button class="copy-btn" data-url="${img.discord_url}" data-feedback="${discordFeedbackId}">Copy Discord URL</button>
                                <div class="copy-feedback" id="${discordFeedbackId}">✓ Copied to clipboard!</div>
                            </div>
                        `;
                    } else {
                        discordUrlHtml = `
                            <div class="url-row">
                                <div class="url-label">Discord URL: <span style="color: #999;">(not yet uploaded)</span></div>
                            </div>
                        `;
                    }
                    
                    card.innerHTML = `
                        <div class="image-preview">
                            <img src="${img.name}" alt="${img.name}" onerror="this.style.display='none'">
                        </div>
                        <div class="image-info">
                            <div class="image-name">${img.name}</div>
                            <div class="url-row">
                                <div class="url-label">Local URL:</div>
                                <div style="display:flex; gap:10px; align-items:center;">
                                    <div style="flex:1">
                                        <div class="image-url" data-url="${img.local_url}">
                                            ${img.local_url}
                                        </div>
                                        <div class="image-size">${formatSize(img.size)}</div>
                                    </div>
                                    <div style="text-align:center; width:120px;">
                                        <img class="qr" data-url="${img.local_url}" alt="QR" style="width:90px; height:90px; border-radius:6px; border:1px solid #e0e0e0; background:white; display:block; margin:0 auto 8px;" />
                                        <a class="open-link" href="${img.local_url}" target="_blank" style="display:inline-block; margin-bottom:6px; color:#667eea; font-size:12px;">Open</a>
                                        <button class="copy-btn" data-url="${img.local_url}" data-feedback="${localFeedbackId}">Copy</button>
                                        <div class="copy-feedback" id="${localFeedbackId}">✓ Copied to clipboard!</div>
                                    </div>
                                </div>
                            </div>
                            ${discordUrlHtml}
                            <div class="image-size">${formatSize(img.size)}</div>
                        </div>
                    `;
                    
                    grid.appendChild(card);
                });
                
                // Generate QR codes for each qr img using Google Chart API (fallback when clipboard not available on insecure origins)
                document.querySelectorAll('img.qr').forEach(q => {
                    try {
                        const u = encodeURIComponent(q.getAttribute('data-url'));
                        q.src = `https://chart.googleapis.com/chart?chs=150x150&cht=qr&chl=${u}`;
                    } catch (e) {
                        // ignore
                    }
                });

                // Add click handlers to all copy buttons and URLs
                document.querySelectorAll('.copy-btn').forEach(btn => {
                    btn.addEventListener('click', function(e) {
                        e.preventDefault();
                        const url = this.getAttribute('data-url');
                        const feedbackId = this.getAttribute('data-feedback');
                        copyToClipboard(url, feedbackId);
                    });
                });
                
                document.querySelectorAll('.image-url').forEach(url => {
                    url.addEventListener('click', function(e) {
                        e.preventDefault();
                        const urlText = this.getAttribute('data-url');
                        const safeId = this.closest('.image-info').querySelector('.image-name').textContent.replace(/[^a-z0-9]/gi, '_');
                        const feedbackId = (this.closest('.url-row').querySelector('.url-label').textContent.includes('Discord') ? 'discord_feedback_' : 'local_feedback_') + safeId;
                        copyToClipboard(urlText, feedbackId);
                    });
                });
            } catch (err) {
                console.error('Failed to load images:', err);
                document.getElementById('images-container').innerHTML = `
                    <div class="empty-state">
                        <h2>⚠️ Error Loading Images</h2>
                        <p>Check browser console for details</p>
                    </div>
                `;
            }
        }
        
        function formatSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }
        
        function copyToClipboard(text, feedbackId) {
            navigator.clipboard.writeText(text)
                .then(() => {
                    const feedback = document.getElementById(feedbackId);
                    if (feedback) {
                        feedback.style.display = 'block';
                        console.log('✓ Copied:', text);
                        setTimeout(() => {
                            feedback.style.display = 'none';
                        }, 2000);
                    }
                })
                .catch(err => {
                    console.error('❌ Failed to copy:', err);
                    // Fallback: try selecting text
                    try {
                        const textArea = document.createElement('textarea');
                        textArea.value = text;
                        document.body.appendChild(textArea);
                        textArea.select();
                        document.execCommand('copy');
                        document.body.removeChild(textArea);
                        
                        const feedback = document.getElementById(feedbackId);
                        if (feedback) {
                            feedback.style.display = 'block';
                            setTimeout(() => {
                                feedback.style.display = 'none';
                            }, 2000);
                        }
                    } catch (e) {
                        alert('Could not copy URL. Please copy manually: ' + text);
                    }
                });
        }
        
        // Load images on page load
        window.addEventListener('load', loadImages);
        // Refresh every 5 seconds to show new images
        setInterval(loadImages, 5000);
    </script>
</body>
</html>
"""
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(html.encode()))
        self.end_headers()
        self.wfile.write(html.encode())
    
    def guess_type(self, path):
        """Guess content type based on file extension"""
        ext = Path(path).suffix.lower()
        types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
        }
        return types.get(ext, 'application/octet-stream')
    
    def log_message(self, format, *args):
        """Log requests to console"""
        print(f"[IMAGE SERVER] {format % args}")


def get_local_ip():
    """Get the local network IP address"""
    import socket
    try:
        # Connect to a non-routable address to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def format_size(bytes_size):
    """Format bytes to human readable size"""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    else:
        return f"{bytes_size / (1024 * 1024):.1f} MB"


def main():
    """Start the image server"""
    PORT = 8889
    
    # Verify images directory exists
    images_dir = Path(__file__).parent / "cogs" / "images"
    if not images_dir.exists():
        print(f"❌ Error: Images directory not found at {images_dir}")
        print("Please create the directory and add images to it.")
        sys.exit(1)
    
    # Get local network IP
    local_ip = get_local_ip()
    
    # Create and start server - bind to 0.0.0.0 for network access
    server = HTTPServer(('0.0.0.0', PORT), ImageHandler)
    
    print("=" * 60)
    print("🖼️  IMAGE SERVER STARTED")
    print("=" * 60)
    print(f"✅ Server running at:")
    print(f"   🖥️  Local:        http://localhost:{PORT}")
    print(f"   🌐 Network:      http://{local_ip}:{PORT}")
    print(f"📁 Serving images from: {images_dir}")
    print()
    print(f"🌐 Open in browser:")
    print(f"   • http://localhost:{PORT} (this computer)")
    print(f"   • http://{local_ip}:{PORT} (network access)")
    print()
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
