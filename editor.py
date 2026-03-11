import subprocess, os, glob, json, datetime, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from email.parser import BytesParser
from email.policy import default

# 自动获取目录
WORKING_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.getenv("PURECOOK_PORT", 8080))
PASSWORD = os.getenv("PURECOOK_PASSWORD", "masterpurecook")

HTML_LOGIN = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><title>PureCook Lab Login</title>
<style>
    body { font-family: system-ui; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f0f2f5; margin: 0; }
    .login-box { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; }
    input { width: 100%; padding: 12px; margin: 15px 0; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; }
    button { background: #1b3022; color: white; border: none; padding: 12px 30px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; }
</style>
</head>
<body>
    <div class="login-box">
        <h1>🌿 PureCook Lab</h1>
        <form method="POST" action="/login">
            <input type="password" name="password" placeholder="Enter System Password" required autofocus>
            <button type="submit">Initialize Editor</button>
        </form>
    </div>
</body></html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><title>PureCook Editor Pro</title>
<style>
    body { font-family: system-ui; max-width: 1200px; margin: 20px auto; padding: 20px; background: #f9f7f2; display: flex; gap: 20px; }
    .sidebar { flex: 1; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); height: fit-content; position: sticky; top: 20px; }
    .main { flex: 2; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
    textarea { width: 100%; height: 600px; font-family: monospace; margin: 10px 0; padding: 15px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; line-height: 1.5; }
    input[type="text"] { width: 100%; padding: 12px; margin: 5px 0; border: 1px solid #ddd; border-radius: 6px; }
    button { background: #1b3022; color: white; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; margin-top: 10px; }
    .edit-btn { background: #d4a373; color: white; padding: 4px 10px; font-size: 0.8rem; text-decoration: none; border-radius: 4px; cursor: pointer; }
    .item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #eee; }
    .upload-section { margin-top: 30px; padding: 15px; background: #f0f4f0; border-radius: 8px; border: 1px dashed #1b3022; }
    .asset-list { font-size: 0.8rem; color: #718096; margin-top: 10px; word-break: break-all; max-height: 200px; overflow-y: auto; }
</style>
<script>
    async function loadToEditor(filename, isRoot) {
        const path = isRoot ? filename : 'articles/' + filename;
        try {
            const res = await fetch('/get_content?file=' + path);
            if (!res.ok) throw new Error('File not found');
            const data = await res.json();
            document.getElementById('title').value = path;
            document.getElementById('body').value = data.content;
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } catch (e) { alert(e.message); }
    }
    function copyUrl(url) {
        navigator.clipboard.writeText(url);
        alert('Path copied: ' + url);
    }
</script>
</head>
<body>
    <div class="sidebar">
        <h2 style="font-family:serif; color:#1b3022;">Inventory</h2>
        <div class="item"><strong>index.html</strong> <a class="edit-btn" onclick="loadToEditor('index.html', true)">Edit</a></div>
        <div class="item"><strong>about.html</strong> <a class="edit-btn" onclick="loadToEditor('about.html', true)">Edit</a></div>
        %ARTICLES%
        <div class="upload-section">
            <h3>📷 Upload Image</h3>
            <form method="POST" action="/upload" enctype="multipart/form-data">
                <input type="file" name="file" accept="image/*" required>
                <button type="submit" style="background:#d4a373;">Sync to Assets</button>
            </form>
            <div class="asset-list">
                <strong>Assets Library:</strong><br>
                %ASSETS%
            </div>
        </div>
        <a href="/logout" style="display:block; margin-top:20px; color:#718096; font-size:0.8rem;">Logout System</a>
    </div>
    <div class="main">
        <h1 style="font-family:serif; color:#1b3022;">Laboratory Editor</h1>
        %MESSAGE%
        <form method="POST" action="/publish">
            <label>Working Path:</label>
            <input type="text" id="title" name="path" placeholder="articles/report.html" required>
            <textarea id="body" name="content" placeholder="Enter report content..." required></textarea>
            <button type="submit">Deploy Changes</button>
        </form>
    </div>
</body></html>
"""

ARTICLE_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>%TITLE% | PureCook Lab Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,700;9..144,800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root { --forest: #1b3022; --bone: #f9f7f2; --sand: #d4a373; --matcha: #e9edc9; --text: #2c362f; --white: #ffffff; --radius: 32px; }
        body { font-family: 'Inter', sans-serif; line-height: 1.8; color: var(--text); background: var(--bone); margin: 0; }
        nav { background: rgba(249, 247, 242, 0.9); backdrop-filter: blur(20px); padding: 1.5rem 0; border-bottom: 1px solid rgba(0,0,0,0.05); position: sticky; top: 0; z-index: 1000; }
        .nav-inner { max-width: 1200px; margin: 0 auto; padding: 0 30px; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-family: 'Fraunces', serif; font-size: 1.6rem; text-decoration: none; color: var(--forest); font-weight: 800; }
        nav a { text-decoration: none; color: var(--text); font-weight: 600; margin-left: 30px; font-size: 0.9rem; opacity: 0.7; }
        .article-hero { background: var(--forest); color: var(--bone); padding: 6rem 0; text-align: center; }
        .tag-pill { background: var(--sand); color: white; padding: 6px 16px; border-radius: 50px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 2rem; display: inline-block; }
        h1 { font-family: 'Fraunces', serif; font-size: 4.5rem; margin: 0 0 1.5rem; line-height: 1; letter-spacing: -3px; }
        .meta { display: flex; align-items: center; justify-content: center; gap: 15px; font-size: 1rem; opacity: 0.8; }
        .author-img { width: 50px; height: 50px; border-radius: 50%; background: url('https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&q=80&w=100') center/cover; border: 3px solid rgba(255,255,255,0.2); }
        .layout-grid { max-width: 1200px; margin: -4rem auto 0; padding: 0 30px 100px; display: grid; grid-template-columns: 1fr 350px; gap: 40px; }
        .article-body { background: var(--white); padding: 60px; border-radius: var(--radius); box-shadow: 0 30px 60px rgba(27, 48, 34, 0.05); }
        .content { font-size: 1.15rem; color: #444; }
        .content h2, .content h3 { font-family: 'Fraunces', serif; color: var(--forest); margin-top: 3rem; }
        .sidebar { position: sticky; top: 120px; height: fit-content; }
        .lab-card { background: var(--forest); color: var(--bone); padding: 40px; border-radius: var(--radius); margin-bottom: 30px; }
        .lab-card h4 { font-family: 'Fraunces', serif; font-size: 1.8rem; margin: 0 0 1rem; color: var(--matcha); }
        .sticky-footer { position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%); background: var(--forest); color: white; padding: 10px 10px 10px 25px; border-radius: 100px; display: flex; align-items: center; gap: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); z-index: 2000; width: fit-content; min-width: 300px; }
        .sticky-btn { background: var(--sand); color: white; padding: 10px 25px; border-radius: 100px; text-decoration: none; font-weight: 800; font-size: 0.85rem; }
        @media (max-width: 1000px) { .layout-grid { grid-template-columns: 1fr; margin-top: 2rem; } .sidebar { display: none; } h1 { font-size: 2.5rem; } .article-body { padding: 30px; } }
    </style>
</head>
<body>
    <nav><div class="nav-inner"><a href="../index.html" class="logo">🌿 PureCook</a><div><a href="../index.html">The Lab</a><a href="../about.html">About</a></div></div></nav>
    <header class="article-hero"><div class="container"><span class="tag-pill">Lab Certified Report</span><h1>%TITLE%</h1><div class="meta"><div class="author-img"></div><span>By <strong>Sarah Miller, PhD</strong> | %DATE%</span></div></div></header>
    <div class="layout-grid">
        <article class="article-body"><div class="content">%CONTENT%</div></article>
        <aside class="sidebar"><div class="lab-card"><h4>🔬 Lab Specs</h4><p><strong>Testing Duration:</strong> 48 Hours<br><strong>Equipment:</strong> XRF Analyzer, Thermal Chamber<br><strong>Integrity:</strong> 100% Independent</p></div></aside>
    </div>
    <div class="sticky-footer"><p>Expert Pick Active</p><a href="#top-pick" class="sticky-btn">View Price</a></div>
    <footer style="padding: 4rem 0; text-align: center; border-top: 1px solid rgba(0,0,0,0.05); color: #718096; font-size: 0.85rem;"><p>&copy; 2026 PureCook Media Group. Clean Cooking. Verified Science.</p></footer>
</body></html>
"""

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class FinalEditor(BaseHTTPRequestHandler):
    session_authenticated = False

    def generate_sitemap(self):
        try:
            urls = ['/', '/about.html']
            for f in glob.glob(os.path.join(WORKING_DIR, "articles", "*.html")):
                urls.append(f"/articles/{os.path.basename(f)}")
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            for url in urls: xml += f'  <url><loc>https://purecook.site{url}</loc><lastmod>{datetime.date.today().isoformat()}</lastmod></url>\n'
            xml += '</urlset>'
            with open(os.path.join(WORKING_DIR, "sitemap.xml"), "w") as f: f.write(xml)
            with open(os.path.join(WORKING_DIR, "robots.txt"), "w") as f: f.write("User-agent: *\nAllow: /\nSitemap: https://purecook.site/sitemap.xml")
        except: pass

    def do_GET(self):
        # 1. 严格路由：防止浏览器插件请求干扰
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == "/":
            if not FinalEditor.session_authenticated:
                self.send_response(200); self.end_headers(); self.wfile.write(HTML_LOGIN.encode('utf-8'))
            else:
                files = [os.path.basename(f) for f in glob.glob(os.path.join(WORKING_DIR, "articles", "*.html"))]
                list_html = "".join([f'<div class="item"><span>{name}</span><a class="edit-btn" onclick="loadToEditor(\'{name}\', false)">Edit</a></div>' for name in sorted(files)])
                assets = [os.path.basename(f) for f in glob.glob(os.path.join(WORKING_DIR, "assets", "*")) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
                asset_links = "".join([f'<div style="margin-bottom:5px;cursor:pointer;color:#1b3022;" onclick="copyUrl(\'assets/{a}\')">• assets/{a}</div>' for a in sorted(assets)])
                self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
                res = HTML_TEMPLATE.replace("%ARTICLES%", list_html).replace("%ASSETS%", asset_links).replace("%MESSAGE%", "")
                self.wfile.write(res.encode('utf-8'))
            return

        if path == "/get_content":
            if not FinalEditor.session_authenticated: self.send_response(403); self.end_headers(); return
            fpath = urllib.parse.parse_qs(parsed_path.query).get('file', [''])[0]
            full_path = os.path.normpath(os.path.join(WORKING_DIR, fpath))
            if not full_path.startswith(os.path.normpath(WORKING_DIR)) or not os.path.exists(full_path):
                self.send_response(404); self.end_headers(); return
            with open(full_path, 'r', encoding='utf-8') as f: content = f.read()
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"content": content}).encode('utf-8'))
            return

        if path == "/logout":
            FinalEditor.session_authenticated = False
            self.send_response(302); self.send_header('Location', '/'); self.end_headers(); return

        # 对于其他所有请求（插件 JS、favicon 等）一律返回 404
        self.send_response(404); self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            if self.path == "/login":
                params = urllib.parse.parse_qs(post_data.decode('utf-8'))
                if params.get("password", [""])[0] == PASSWORD: FinalEditor.session_authenticated = True
                self.send_response(302); self.send_header('Location', '/'); self.end_headers(); return

            if not FinalEditor.session_authenticated: self.send_response(403); self.end_headers(); return

            msg_text = ""
            if self.path == "/upload":
                headers = f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode('ascii')
                msg = BytesParser(policy=default).parsebytes(headers + post_data)
                for part in msg.iter_parts():
                    if part.get_filename():
                        fn = os.path.basename(part.get_filename())
                        with open(os.path.join(WORKING_DIR, "assets", fn), 'wb') as f: f.write(part.get_payload(decode=True))
                        self.generate_sitemap(); msg_text = f"Uploaded {fn}"; break
            else:
                params = urllib.parse.parse_qs(post_data.decode('utf-8'))
                path, content = params.get("path", [""])[0], params.get("content", [""])[0]
                if not content.strip().lower().startswith("<!doctype html"):
                    title = os.path.basename(path).replace(".html", "").replace("-", " ").title()
                    content = ARTICLE_PAGE_TEMPLATE.replace("%TITLE%", title).replace("%CONTENT%", content).replace("%DATE%", datetime.date.today().strftime("%B %d, %Y"))
                full_path = os.path.normpath(os.path.join(WORKING_DIR, path))
                if full_path.startswith(os.path.normpath(WORKING_DIR)):
                    with open(full_path, "w", encoding='utf-8') as f: f.write(content)
                    self.generate_sitemap(); msg_text = f"Published {path}"

            self.send_response(200); self.end_headers()
            res = HTML_TEMPLATE.replace("%ARTICLES%", "").replace("%ASSETS%", "").replace("%MESSAGE%", f'<p style="color:green">🚀 {msg_text}</p><a href="/">Back</a>')
            self.wfile.write(res.encode('utf-8'))
        except Exception as e:
            self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())

if __name__ == "__main__":
    print(f"PureCook Editor Pro [Multithreaded] starting on port {PORT}...")
    server = ThreadedHTTPServer(('0.0.0.0', PORT), FinalEditor)
    server.serve_forever()
