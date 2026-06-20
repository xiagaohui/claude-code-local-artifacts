#!/usr/bin/env python3
"""
local-artifacts: Claude Code Artifacts 本地高仿版（非官方实现）
高仿官方 Artifacts 的使用体验，本地 HTTP 服务承载，支持 HTML 和 Markdown，SSE 实时刷新。
注意：与官方架构不同——官方是云端无后端静态页，本版是本地带后端服务，仅模仿用户体验。

- MCP tool: publish_artifact
- HTTP server: http://localhost:7891
- Markdown 用本地 marked.js 客户端渲染（内联，无外网依赖，内网可用）
"""

import asyncio
import html
import json
import os
import queue
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
PORT = int(os.environ.get("ARTIFACTS_PORT", "7891"))  # 可用环境变量覆盖
MAX_SIZE = 16 * 1024 * 1024  # 16 MiB，对齐官方渲染大小约束
ARTIFACTS_DIR = Path.home() / ".claude" / "artifacts"
STATE_FILE = ARTIFACTS_DIR / "state.json"          # 元数据（轻量）
CONTENT_FILE = ARTIFACTS_DIR / "current_content.json"  # 全量内容（持久化，重启可恢复）
MARKED_JS_PATH = Path(__file__).parent / "marked.min.js"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# 启动时内联读取本地 marked.js（无 CDN 依赖，内网/离线可用）
try:
    MARKED_JS = MARKED_JS_PATH.read_text(encoding="utf-8")
except Exception:
    MARKED_JS = ""

# ── Shared state ──────────────────────────────────────────────────────────────
_state: dict = {
    "title": "",
    "emoji": "📄",
    "content": "",
    "format": "html",
    "published_at": "",
}
_sse_clients: list = []
_state_lock = threading.Lock()
_sse_lock = threading.Lock()       # 专门保护 _sse_clients 并发增删/遍历
_http_error: str = ""              # HTTP 线程启动失败时记录，供 publish 如实报错


def _load_persisted_state():
    """启动时从磁盘恢复上次发布的 artifact（重启后 /artifact 仍可打开）"""
    try:
        if CONTENT_FILE.exists():
            saved = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                _state.update({k: saved.get(k, _state[k]) for k in _state})
    except Exception:
        pass


_load_persisted_state()

# ── HTML templates ────────────────────────────────────────────────────────────

SSE_SCRIPT = """
<script>
(function(){
  var es = new EventSource('/events');
  es.onmessage = function(){ window.location.reload(); };
  es.onerror = function(){ setTimeout(function(){ window.location.reload(); }, 3000); };
})();
</script>
"""

BANNER_CSS = """
<style>
#_ab {
  position:fixed;top:0;left:0;right:0;
  background:#1e1e2e;color:#cdd6f4;
  font:12px/34px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  padding:0 16px;z-index:99999;display:flex;gap:12px;align-items:center;
  border-bottom:1px solid #313244;
  box-shadow:0 1px 8px rgba(0,0,0,.3);
}
#_ab ._title{font-weight:600;color:#89b4fa;}
#_ab ._sep{opacity:.3;}
#_ab ._time{opacity:.5;font-size:11px;}
#_ab ._dot{
  width:8px;height:8px;border-radius:50%;background:#a6e3a1;
  animation:_pulse 2s infinite;
}
@keyframes _pulse{0%,100%{opacity:1;}50%{opacity:.4;}}
body{padding-top:38px!important;box-sizing:border-box;}
</style>
"""

MARKDOWN_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      color:#24292f;max-width:900px;margin:0 auto;padding:2rem;line-height:1.6;}}
h1,h2,h3,h4{{margin-top:1.5em;border-bottom:1px solid #d0d7de;padding-bottom:.3em;}}
h1{{border-bottom:2px solid #d0d7de;}}
code{{font-family:'SFMono-Regular',Consolas,monospace;font-size:.9em;
      background:#f6f8fa;padding:.2em .4em;border-radius:4px;}}
pre{{background:#f6f8fa;padding:1rem;border-radius:6px;overflow-x:auto;}}
pre code{{background:none;padding:0;}}
blockquote{{border-left:4px solid #d0d7de;margin:0;padding:0 1em;color:#57606a;}}
table{{border-collapse:collapse;width:100%;margin:1em 0;}}
th,td{{border:1px solid #d0d7de;padding:6px 13px;}}
th{{background:#f6f8fa;font-weight:600;}}
tr:nth-child(2n){{background:#f6f8fa;}}
img{{max-width:100%;}}
a{{color:#0969da;}}
hr{{border:none;border-top:1px solid #d0d7de;margin:2em 0;}}
</style>
</head>
<body>
{banner}
<div id="_content"></div>
<script>{marked_js}</script>
<script>
var _md = {escaped_content};
document.getElementById('_content').innerHTML =
  (typeof marked !== 'undefined')
    ? marked.parse(_md)
    : '<pre>'+_md.replace(/&/g,'&amp;').replace(/</g,'&lt;')+'</pre>';
</script>
{sse}
</body>
</html>"""


def _banner_html(title: str, emoji: str, published_at: str) -> str:
    """生成 banner（含 CSS）。title/emoji 做 HTML 转义防注入。"""
    st = html.escape(title)
    se = html.escape(emoji)
    sp = html.escape(published_at)
    return (
        f'{BANNER_CSS}'
        f'<div id="_ab">'
        f'<span class="_dot"></span>'
        f'<span>{se}</span>'
        f'<span class="_title">{st}</span>'
        f'<span class="_sep">·</span>'
        f'<span class="_time">local artifact · {sp}</span>'
        f'</div>'
    )


def build_html_page(title: str, emoji: str, content: str, published_at: str) -> str:
    """包装 HTML 内容：注入 banner + SSE（banner 自带 CSS，不重复注入）"""
    banner = _banner_html(title, emoji, published_at)
    lo = content.lower()
    # 完整 HTML 文档：注入到 </body> 前
    if "</body>" in lo:
        close_body = lo.rfind("</body>")
        return content[:close_body] + banner + SSE_SCRIPT + content[close_body:]
    # 有 <body> 无闭合：注入到 </html> 前（若有），否则末尾追加
    if "<body" in lo:
        if "</html>" in lo:
            close_html = lo.rfind("</html>")
            return content[:close_html] + banner + SSE_SCRIPT + content[close_html:]
        return content + banner + SSE_SCRIPT
    # 纯 HTML 片段：包一层文档外壳
    st = html.escape(title)
    se = html.escape(emoji)
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{se} {st}</title>
</head>
<body>
{banner}
{content}
{SSE_SCRIPT}
</body>
</html>"""


def build_markdown_page(title: str, emoji: str, content: str, published_at: str) -> str:
    """Markdown 用内联 marked.js 客户端渲染。

    安全：json.dumps 防 JS 字符串语法破坏，额外 replace('</','<\\/')
    防 HTML 解析器提前闭合 <script>（</script> 逃逸 XSS）。
    """
    banner = _banner_html(title, emoji, published_at)
    escaped = json.dumps(content).replace("</", "<\\/")
    full_title = f"{html.escape(emoji)} {html.escape(title)}"
    return MARKDOWN_PAGE.format(
        title=full_title,
        banner=banner,
        marked_js=MARKED_JS,
        escaped_content=escaped,
        sse=SSE_SCRIPT,
    )


def build_page(state: dict) -> str:
    title = state.get("title", "Artifact")
    emoji = state.get("emoji", "📄")
    content = state.get("content", "")
    fmt = state.get("format", "html")
    ts = state.get("published_at", "")
    if fmt == "markdown":
        return build_markdown_page(title, emoji, content, ts)
    return build_html_page(title, emoji, content, ts)


EMPTY_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Artifacts</title>
<style>
body{font-family:-apple-system,sans-serif;display:flex;align-items:center;
     justify-content:center;height:100vh;margin:0;background:#f6f8fa;color:#57606a;}
.box{text-align:center;padding:2rem;}
h2{color:#24292f;margin-bottom:.5rem;}
code{background:#eee;padding:.2em .5em;border-radius:4px;font-size:.95em;}
</style></head>
<body><div class="box">
<h2>📄 No artifact yet</h2>
<p>Ask Claude to publish one:<br>
<code>把这个结果做成 artifact 发布</code></p>
</div></body></html>"""

# ── SSE helpers ───────────────────────────────────────────────────────────────

def _notify_sse():
    ts = str(int(time.time()))
    with _sse_lock:
        clients = list(_sse_clients)
    for q in clients:
        try:
            q.put_nowait(ts)
        except Exception:
            pass  # 满了说明客户端卡住，交给 /events 线程自己超时清理


# ── HTTP server ───────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # MCP 用 stdio，不能污染 stdout

    def do_POST(self):
        """接收 publish 请求：{ title, content, format, emoji }"""
        path = self.path.split("?")[0]
        if path != "/publish":
            self._send(404, "text/plain", b"Not found")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_SIZE:
                self._send(413, "application/json",
                           b'{"ok":false,"error":"content exceeds 16 MiB"}')
                return
            body = self.rfile.read(length)
            data = json.loads(body)
            if not isinstance(data, dict):
                self._send(400, "application/json",
                           b'{"ok":false,"error":"body must be a JSON object"}')
                return
            _publish(
                title=data.get("title", "Artifact"),
                emoji=data.get("emoji", "📄"),
                content=data.get("content", ""),
                fmt=data.get("format", "html"),
                published_at=data.get("published_at", ""),
            )
            self._send(200, "application/json", b'{"ok":true}')
        except Exception as e:
            msg = json.dumps({"ok": False, "error": str(e)[:200]})
            self._send(400, "application/json", msg.encode())

    def do_GET(self):
        path = self.path.split("?")[0]

        if path in ("/", "/artifact", "/artifact/latest"):
            with _state_lock:
                s = dict(_state)
            if not s.get("content"):
                self._send(200, "text/html; charset=utf-8", EMPTY_PAGE.encode())
                return
            html_bytes = build_page(s).encode("utf-8")
            self._send(200, "text/html; charset=utf-8", html_bytes)

        elif path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            q: queue.Queue = queue.Queue(maxsize=8)
            with _sse_lock:
                _sse_clients.append(q)
            try:
                while True:
                    try:
                        msg = q.get(timeout=25)
                        self.wfile.write(f"data: {msg}\n\n".encode())
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            finally:
                with _sse_lock:
                    try:
                        _sse_clients.remove(q)
                    except ValueError:
                        pass

        elif path == "/status":
            with _state_lock:
                s = dict(_state)
            s.pop("content", None)
            s["http_error"] = _http_error
            self._send(200, "application/json",
                       json.dumps(s, ensure_ascii=False).encode())

        else:
            self._send(404, "text/plain", b"Not found")

    def _send(self, code: int, ct: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _publish(title: str, emoji: str, content: str, fmt: str, published_at: str):
    """更新共享状态 + 持久化 + 通知 SSE。供 HTTP POST 和 MCP 工具共用。"""
    now = published_at or time.strftime("%Y-%m-%d %H:%M:%S")
    with _state_lock:
        _state.update({
            "title": title,
            "emoji": emoji,
            "content": content,
            "format": fmt,
            "published_at": now,
        })
        snap = dict(_state)
    # 持久化：元数据 + 全量内容（重启后可恢复）
    try:
        meta = {k: v for k, v in snap.items() if k != "content"}
        STATE_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
        CONTENT_FILE.write_text(json.dumps(snap, ensure_ascii=False))
    except Exception:
        pass  # 持久化失败不影响主流程（内容已在内存）
    _notify_sse()


def _run_http():
    global _http_error
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
        server.serve_forever()
    except OSError as e:
        _http_error = f"端口 {PORT} 绑定失败：{e}（可能已有服务器在运行）"


def _open_browser(url: str):
    """跨平台打开浏览器"""
    if sys.platform == "darwin":
        cmd = ["open", url]
    elif sys.platform.startswith("linux"):
        cmd = ["xdg-open", url]
    elif sys.platform.startswith("win"):
        cmd = ["cmd", "/c", "start", "", url]
    else:
        return
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ── MCP server ────────────────────────────────────────────────────────────────

async def _run_mcp():
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent

    app = Server("local-artifacts")

    @app.list_tools()
    async def list_tools():
        return [
            Tool(
                name="publish_artifact",
                description=(
                    "把当前 session 的工作成果发布为本地实时交互页面。"
                    "支持 HTML 和 Markdown，每次发布同一 URL 原地刷新，无需重新打开。"
                    "适用场景：PR 走查、数据看板、方案对比、调试时间线、进度 checklist。"
                    f"发布后自动打开浏览器 http://localhost:{PORT}。"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string",
                                  "description": "页面标题，显示在 banner 和浏览器标签页"},
                        "content": {"type": "string",
                                    "description": "要发布的 HTML 或 Markdown 内容"},
                        "format": {"type": "string", "enum": ["html", "markdown"],
                                   "description": "内容格式，默认 html", "default": "html"},
                        "emoji": {"type": "string",
                                  "description": "页面 emoji 图标，默认 📄"},
                        "file_path": {"type": "string",
                                      "description": "本地 .html/.htm/.md 文件路径（content 的替代）"},
                    },
                    "required": ["title"],
                },
            )
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name != "publish_artifact":
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        title     = arguments.get("title", "Artifact")
        emoji     = arguments.get("emoji", "📄")
        fmt       = arguments.get("format", "html")
        content   = arguments.get("content", "")
        file_path = arguments.get("file_path", "")

        # 从文件读取（含大小校验）
        if file_path and not content:
            try:
                p = Path(file_path).expanduser().resolve()
                size = p.stat().st_size
                if size > MAX_SIZE:
                    return [TextContent(type="text",
                        text=f"❌ 文件过大（{size//1024//1024} MiB），超过 16 MiB 上限")]
                content = p.read_text(encoding="utf-8")
                if p.suffix.lower() in (".md", ".markdown"):
                    fmt = "markdown"
                elif p.suffix.lower() in (".html", ".htm"):
                    fmt = "html"
            except Exception as e:
                return [TextContent(type="text", text=f"❌ 读取文件失败: {e}")]

        if not content:
            return [TextContent(type="text", text="❌ 需要提供 content 或 file_path 参数")]

        if len(content.encode("utf-8")) > MAX_SIZE:
            return [TextContent(type="text",
                text="❌ 内容超过 16 MiB 上限，请精简（大图建议用 SVG 或外链）")]

        # HTTP 服务器没起来 → 如实报错，不谎报成功
        if _http_error:
            return [TextContent(type="text",
                text=f"⚠️ 内容已记录，但本地服务异常：{_http_error}\n"
                     f"请检查 7891 端口或重启 Claude Code。")]

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        _publish(title=title, emoji=emoji, content=content, fmt=fmt, published_at=now)
        _open_browser(f"http://localhost:{PORT}")

        return [TextContent(type="text", text=(
            f"✅ Artifact 已发布\n"
            f"  URL：http://localhost:{PORT}\n"
            f"  标题：{emoji} {title}\n"
            f"  格式：{fmt}\n"
            f"  时间：{now}\n\n"
            f"浏览器已自动打开。输入 /artifact 可随时重新打开。"
        ))]

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    t = threading.Thread(target=_run_http, daemon=True)
    t.start()
    try:
        asyncio.run(_run_mcp())
    except KeyboardInterrupt:
        pass
