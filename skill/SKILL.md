---
name: artifact
description: 打开最新发布的 Artifact 页面（http://localhost:7891）。本地高仿版 Artifacts 的查看入口，类似官方 Ctrl+] 重开快捷键。当用户说「打开 artifact」「看一下 artifact」「/artifact」时触发。Open the latest published local artifact page.
---

# Local Artifact Viewer (unofficial local look-alike)

Open the most recently published artifact in the browser.

> This is the **local, unofficial** look-alike of Claude Code Artifacts.
> It mimics the official UX but runs a small local HTTP server instead of
> the cloud, no-backend design used by the official feature.

## Open the latest artifact

```bash
open "http://localhost:${ARTIFACTS_PORT:-7891}" 2>/dev/null \
  || xdg-open "http://localhost:${ARTIFACTS_PORT:-7891}" 2>/dev/null \
  || python3 -c "import webbrowser,os;webbrowser.open('http://localhost:'+os.environ.get('ARTIFACTS_PORT','7891'))"
```

If the page is empty, nothing has been published yet. Tell Claude:

```
把这个结果做成 artifact 发布     (or: "make this into an artifact")
```

Claude will call the `publish_artifact` MCP tool, which opens the browser and
updates the page in place on every publish.

## Check service status

```bash
PORT="${ARTIFACTS_PORT:-7891}"
curl -s "http://localhost:${PORT}/status" 2>/dev/null | python3 -c "
import json,sys
try:
    d = json.load(sys.stdin)
    print('✅ service running')
    if d.get('title'):
        print(f'   latest: {d.get(\"emoji\",\"\")} {d[\"title\"]} @ {d.get(\"published_at\",\"\")}')
    else:
        print('   no artifact published yet')
    if d.get('http_error'):
        print('   ⚠️ ', d['http_error'])
except Exception:
    print('❌ service not reachable — restart Claude Code so the MCP server starts')
"
```
