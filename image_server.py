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
                meta.innerHTML = `<strong class="embed-title">${img.name}</strong><div style="margin-top:4px">${(img.size/1024).toFixed(1)} KB</div>`;
                card.appendChild(meta);

                const buttons = document.createElement('div'); buttons.className='buttons';

                const copyLocal = document.createElement('button'); copyLocal.textContent='Copy Local URL'; copyLocal.className='btn-copy';
                copyLocal.onclick = ()=>{ copyTextExec(img.local_url, 'Local URL copied'); };
                buttons.appendChild(copyLocal);

                if(img.discord_url){
                    const copyDiscord = document.createElement('button'); copyDiscord.textContent='Copy Discord URL'; copyDiscord.className='btn-copy secondary';
                    copyDiscord.onclick = ()=>{ copyTextExec(img.discord_url, 'Discord URL copied'); };
                    buttons.appendChild(copyDiscord);
                }

                const copyData = document.createElement('button'); copyData.textContent='Copy Python Line'; copyData.className='btn-copy';
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
