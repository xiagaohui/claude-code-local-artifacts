# Claude Code Local Artifacts

**English** | [简体中文](./README.zh-CN.md)

> A local, open-source look‑alike of Claude Code's **Artifacts** feature — for personal accounts that can't use the official one.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

Turn Claude Code's work into a **live, interactive web page** at a local URL that updates in place as your session continues.

This is an **independent local re-implementation** of an Artifacts-style workflow. It does **not** access, unlock, modify, or proxy Anthropic's official Artifacts service — it only renders content your own local Claude Code session produces, on your own machine.

```
You: "把这个分析做成 artifact 发布"   →   Claude generates a page
     →  publishes to http://localhost:7891  →  browser opens
     →  say "更新一下" → page reloads in place (SSE live refresh)
```

---

## ⚠️ Unofficial — read this first

This project is **NOT** Anthropic's official Artifacts feature and is **not affiliated with Anthropic**. It only **imitates the user-facing experience**. The internals are fundamentally different:

| | Official Artifacts | This project |
|---|---|---|
| Hosting | `claude.ai/code/artifact/…` (cloud) | `localhost:7891` (your machine) |
| Backend | **None** — static page under CSP | **Has** a small Python backend |
| Implementation | Built into Claude Code | A standalone MCP server |
| Plan required | Team / Enterprise | **Any** (personal/API) |
| Sharing / versions / audit | Yes | No (single user, latest version only) |

If you have a Team/Enterprise plan, use the [official feature](https://code.claude.com/docs/en/artifacts) instead — it's better and properly sandboxed.

**What this is good for:** personal accounts, API-key users, or anyone who just wants "make my Claude Code session output a shareable local page."

---

## Features

- 🎯 **One command** — say "make an artifact" in any Claude Code session
- 🔄 **Live refresh** — same URL updates in place via Server-Sent Events
- 📝 **HTML + Markdown** — Markdown rendered by bundled `marked.js` (no CDN; works fully offline / on intranets)
- 🔒 **XSS-hardened** — `</script>` escaping + HTML-escaped titles
- 💾 **Persistent** — reopens your last artifact after a restart
- 📦 **Self-contained** — one Python file + one JS file, only dependency is `mcp`

## Requirements

- macOS / Linux / Windows
- Python 3.10+
- Claude Code
- Python package: `mcp`

## Install

```bash
git clone https://github.com/xiagaohui/claude-code-local-artifacts.git
cd claude-code-local-artifacts
./install.sh
```

The script will:
1. Create a virtualenv and install `mcp`
2. Register the `local-artifacts` MCP server with Claude Code
3. Install the `/artifact` skill

Then **restart Claude Code**. Done.

<details>
<summary>Manual install (if you don't trust the script)</summary>

```bash
# 1. install the mcp dependency into a venv
python3 -m venv .venv
.venv/bin/pip install mcp

# 2. register the MCP server (adjust the absolute path)
claude mcp add local-artifacts \
  "$(pwd)/.venv/bin/python" "$(pwd)/server.py"

# 3. (optional) install the /artifact reopen skill
mkdir -p ~/.claude/skills/artifact
cp skill/SKILL.md ~/.claude/skills/artifact/SKILL.md

# 4. restart Claude Code
```
</details>

## Usage

In any Claude Code session:

```
把这个结果做成 artifact 发布            # publish as an artifact
帮我做一个 PR 走查 artifact，展示 diff   # PR walk-through
做一个数据看板 artifact                  # dashboard
更新一下 artifact，加上 xxx              # update in place
```

Reopen the latest artifact anytime:

```
/artifact
```

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `ARTIFACTS_PORT` | `7891` | HTTP server port |

## How it works

```
Claude Code ──(MCP stdio)──> server.py ──┬── publish_artifact tool
                                          └── ThreadingHTTPServer :7891
                                                ├── GET /          → rendered page
                                                ├── GET /events    → SSE live-reload
                                                └── POST /publish   → update content
Browser ──> http://localhost:7891 ──(EventSource)──> auto-reload on publish
```

## Security

Please read before installing:

- **It renders arbitrary HTML/JS.** An artifact is a page built from content your Claude Code session produces, served at `http://localhost:7891`. Opening it **executes that HTML/JavaScript in your browser** — treat it like running untrusted front-end code. Only publish content you trust.
- **Localhost only.** The server binds to `127.0.0.1`, so it is **not** reachable from your LAN/Wi-Fi. Don't expose the port (e.g. via a tunnel) to untrusted networks.
- **`file_path` is restricted.** The `publish_artifact` tool only reads document files (`.html/.htm/.md/.markdown/.txt`); it refuses other paths to avoid leaking files like `~/.ssh/id_rsa` or `.env` if a prompt tries to make it.
- **Local state is private.** Published content is cached under `~/.claude/artifacts/` with `0600` permissions (dir `0700`).
- **No sandbox.** Unlike the official feature (CSP-isolated), this has no content sandbox. That's the price of running it yourself on a personal account.

Use it for your own work on your own machine. Don't point it at content from untrusted sources.

## Limitations vs. official

Intentionally omitted (not needed for personal single-machine use): org sharing, version history & picker, author gallery, audit logs, CSP sandboxing, retention policies, Compliance API. See the comparison table above.

## Credits

- Markdown rendering by [marked](https://github.com/markedjs/marked) (MIT) — bundled as `marked.min.js`.
- Inspired by [Claude Code Artifacts](https://code.claude.com/docs/en/artifacts).

## License

[MIT](./LICENSE)
