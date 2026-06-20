# Local Artifacts for Claude Code

**简体中文** | [English](./README.md)

> Claude Code 官方 **Artifacts** 功能的本地开源高仿版——给用不了官方功能（需 Team/Enterprise）的个人账号用。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

把 Claude Code 一次 session 的工作成果变成一个**本地实时交互网页**，随 session 进展原地刷新。

这是一个**独立的本地实现**，**不访问、不解锁、不修改、不代理** Anthropic 官方的 Artifacts 服务——只在你自己的电脑上，渲染你自己的 Claude Code session 产出的内容。

```
你说："把这个分析做成 artifact 发布"   →   Claude 生成页面
     →  发布到 http://localhost:7891   →  浏览器自动打开
     →  说"更新一下" → 页面原地刷新（SSE 实时推送）
```

---

## ⚠️ 非官方——请先读这段

本项目**不是** Anthropic 官方的 Artifacts 功能，**与 Anthropic 无关**，只**模仿用户体验**。底层架构完全不同：

| | 官方 Artifacts | 本项目 |
|---|---|---|
| 托管 | `claude.ai/code/artifact/…`（云端） | `localhost:7891`（你的电脑） |
| 后端 | **无** —— CSP 沙箱下的静态页 | **有** —— 一个小型 Python 后端 |
| 实现 | 内置于 Claude Code | 独立的 MCP server |
| 套餐要求 | Team / Enterprise | **任意**（个人 / API） |
| 分享 / 版本 / 审计 | 有 | 无（单用户，仅保留最新版） |

如果你有 Team/Enterprise 套餐，请直接用[官方功能](https://code.claude.com/docs/en/artifacts)——它更好，而且有正规的安全沙箱。

**这个项目适合谁：** 个人账号、API key 用户，或任何只想"把 Claude Code 的 session 输出变成可分享的本地页面"的人。

---

## 功能特点

- 🎯 **一句话触发** —— 在任意 Claude Code session 里说"做成 artifact"
- 🔄 **实时刷新** —— 同一 URL 通过 Server-Sent Events 原地更新
- 📝 **HTML + Markdown** —— Markdown 由内置的 `marked.js` 渲染（无 CDN，**完全离线 / 内网可用**）
- 🔒 **XSS 加固** —— `</script>` 转义 + 标题 HTML 转义
- 💾 **持久化** —— 重启后仍能打开上次的 artifact
- 📦 **自包含** —— 一个 Python 文件 + 一个 JS 文件，唯一依赖是 `mcp`

## 环境要求

- macOS / Linux / Windows
- Python 3.10+
- Claude Code
- Python 包：`mcp`

## 安装

```bash
git clone https://github.com/xiagaohui/local-artifacts-for-claude-code.git
cd local-artifacts-for-claude-code
./install.sh
```

脚本会自动：
1. 创建虚拟环境并安装 `mcp`
2. 把 `local-artifacts` MCP server 注册到 Claude Code
3. 安装 `/artifact` 重开命令

然后**重启 Claude Code** 即可。

<details>
<summary>手动安装（如果你不放心脚本）</summary>

```bash
# 1. 在虚拟环境里装 mcp 依赖
python3 -m venv .venv
.venv/bin/pip install mcp

# 2. 注册 MCP server（注意用绝对路径）
claude mcp add local-artifacts \
  "$(pwd)/.venv/bin/python" "$(pwd)/server.py"

# 3.（可选）安装 /artifact 重开命令
mkdir -p ~/.claude/skills/artifact
cp skill/SKILL.md ~/.claude/skills/artifact/SKILL.md

# 4. 重启 Claude Code
```
</details>

## 用法

在任意 Claude Code session 里：

```
把这个结果做成 artifact 发布            # 发布为 artifact
帮我做一个 PR 走查 artifact，展示 diff   # PR 走查
做一个数据看板 artifact                  # 数据看板
更新一下 artifact，加上 xxx              # 原地更新
```

随时重新打开最新的 artifact：

```
/artifact
```

## 配置

| 环境变量 | 默认值 | 含义 |
|---|---|---|
| `ARTIFACTS_PORT` | `7891` | HTTP 服务端口 |
| `CLAUDE_CODE_ARTIFACT_AUTO_OPEN` | `1` | 设为 `0` 关闭发布时自动打开浏览器（对齐官方同名变量）|
| `CLAUDE_CODE_DISABLE_ARTIFACT` | 未设置 | 设为 `1` 完全禁用发布（对齐官方同名变量）|

## 工作原理

```
Claude Code ──(MCP stdio)──> server.py ──┬── publish_artifact 工具
                                          └── ThreadingHTTPServer :7891
                                                ├── GET /          → 渲染后的页面
                                                ├── GET /events    → SSE 实时刷新
                                                └── POST /publish   → 更新内容
浏览器 ──> http://localhost:7891 ──(EventSource)──> 发布时自动刷新
```

## 安全说明

安装前请阅读：

- **它会渲染任意 HTML/JS。** Artifact 是由你的 Claude Code session 产出的内容生成的页面，在 `http://localhost:7891` 渲染。打开它就会**在浏览器里执行这些 HTML/JavaScript**——等同于运行不受信的前端代码。**只发布你信任的内容。**
- **仅本机可访问。** 服务绑定 `127.0.0.1`，局域网/同一 WiFi 的人**无法**访问。不要通过隧道把端口暴露到不可信网络。
- **`file_path` 已限制。** `publish_artifact` 工具只读文档文件（`.html/.htm/.md/.markdown/.txt`），拒绝其他路径，防止 prompt 诱导读取 `~/.ssh/id_rsa`、`.env` 等敏感文件并外泄。
- **本地状态私有。** 发布内容缓存在 `~/.claude/artifacts/`，文件权限 `0600`、目录 `0700`。
- **无沙箱。** 与官方（CSP 隔离）不同，本工具没有内容沙箱——这是在个人账号上自建的代价。

请用它处理你自己电脑上的工作，不要拿它渲染来源不可信的内容。

## 与官方的差异

有意省略的能力（个人单机使用不需要）：组织分享、版本历史与版本选择器、作者作品集、审计日志、CSP 沙箱、保留策略、Compliance API。详见上方对比表。

## 致谢

- Markdown 渲染由 [marked](https://github.com/markedjs/marked)（MIT）提供 —— 以 `marked.min.js` 形式内置打包。
- 灵感来自 [Claude Code Artifacts](https://code.claude.com/docs/en/artifacts)。

## 许可证

[MIT](./LICENSE)
