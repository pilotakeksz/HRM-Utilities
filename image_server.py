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
            
            data = {
                "server_ip": server_ip,
                "port": 8889,
                "server_url": f"http://{server_ip}:8889",
                "images": [
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "url": f"http://{server_ip}:8889/{f.name}"
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
            cursor: pointer;
            transition: background 0.2s;
            line-height: 1.4;
            max-height: 60px;
            overflow-y: auto;
        }
        .image-url:hover {
            background: #e0e0e0;
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
                    
                    const feedbackId = 'feedback-' + img.name.replace(/[^a-z0-9]/gi, '_');
                    
                    card.innerHTML = `
                        <div class="image-preview">
                            <img src="${img.name}" alt="${img.name}" onerror="this.style.display='none'">
                        </div>
                        <div class="image-info">
                            <div class="image-name">${img.name}</div>
                            <div class="image-url" onclick="copyToClipboard('${img.url}', '${feedbackId}')">
                                ${img.url}
                            </div>
                            <div class="image-size">${formatSize(img.size)}</div>
                            <button class="copy-btn" onclick="copyToClipboard('${img.url}', '${feedbackId}')">Copy URL</button>
                            <div class="copy-feedback" id="${feedbackId}">✓ Copied to clipboard!</div>
                        </div>
                    `;
                    grid.appendChild(card);
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
            navigator.clipboard.writeText(text).then(() => {
                const feedback = document.getElementById(feedbackId);
                if (feedback) {
                    feedback.style.display = 'block';
                    setTimeout(() => {
                        feedback.style.display = 'none';
                    }, 2000);
                }
            }).catch(err => {
                console.error('Failed to copy:', err);
                alert('Failed to copy URL to clipboard');
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
