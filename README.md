# Claude Code Local Artifacts

> A local, open-source look‑alike of Claude Code's **Artifacts** feature — for personal accounts that can't use the official one.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

Turn Claude Code's work into a **live, interactive web page** at a local URL that updates in place as your session continues — without a Team/Enterprise plan.

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

## Limitations vs. official

Intentionally omitted (not needed for personal single-machine use): org sharing, version history & picker, author gallery, audit logs, CSP sandboxing, retention policies, Compliance API. See the comparison table above.

## Credits

- Markdown rendering by [marked](https://github.com/markedjs/marked) (MIT) — bundled as `marked.min.js`.
- Inspired by [Claude Code Artifacts](https://code.claude.com/docs/en/artifacts).

## License

[MIT](./LICENSE)

---

<details>
<summary>🇨🇳 中文说明</summary>

## 这是什么

Claude Code 官方 **Artifacts** 功能的**本地高仿版**——给用不了官方功能（需 Team/Enterprise）的个人账号用。

把 Claude Code 一次 session 的工作成果变成一个**本地实时交互网页**，随 session 进展原地刷新。

## ⚠️ 非官方

这**不是** Anthropic 官方功能，与 Anthropic 无关，只**模仿用户体验**。底层架构完全不同：官方是云端无后端静态页，本项目是本地带 Python 后端。有 Team/Enterprise 的请直接用[官方功能](https://code.claude.com/docs/en/artifacts)。

## 安装

```bash
git clone https://github.com/xiagaohui/claude-code-local-artifacts.git
cd claude-code-local-artifacts
./install.sh
# 然后重启 Claude Code
```

## 用法

对话里直接说「把这个做成 artifact 发布」，浏览器自动打开 `http://localhost:7891`，说「更新一下 artifact」原地刷新。`/artifact` 随时重开。

## 特点

- marked.js 内联打包，**内网/离线可用**
- XSS 防护、16MiB 限制、断电持久化、跨平台
- 单文件 Python，唯一依赖 `mcp`

</details>
