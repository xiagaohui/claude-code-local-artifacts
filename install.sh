#!/usr/bin/env bash
#
# Installer for claude-code-local-artifacts
# - creates a venv with the `mcp` dependency
# - registers the MCP server with Claude Code
# - installs the /artifact reopen skill
#
set -euo pipefail

# Resolve this script's directory (the repo root)
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
SERVER_PY="$REPO_DIR/server.py"

echo "==> claude-code-local-artifacts installer"
echo "    repo: $REPO_DIR"

# 1. Find a Python 3.10+
PY=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    PY="$(command -v "$cand")"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "ERROR: Python 3.10+ not found. Please install Python first." >&2
  exit 1
fi
echo "==> Using Python: $PY ($("$PY" --version 2>&1))"

# 2. Create venv + install mcp
if [ ! -d "$VENV_DIR" ]; then
  echo "==> Creating virtualenv at $VENV_DIR"
  "$PY" -m venv "$VENV_DIR"
fi
echo "==> Installing dependency: mcp"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"
VENV_PY="$VENV_DIR/bin/python"

# 3. Register the MCP server with Claude Code
if command -v claude >/dev/null 2>&1; then
  echo "==> Registering MCP server 'local-artifacts' with Claude Code"
  # remove any stale registration, then add fresh (ignore errors if not present)
  claude mcp remove local-artifacts >/dev/null 2>&1 || true
  claude mcp add local-artifacts "$VENV_PY" "$SERVER_PY"
else
  echo "WARNING: 'claude' CLI not found on PATH. Register manually:" >&2
  echo "  claude mcp add local-artifacts \"$VENV_PY\" \"$SERVER_PY\"" >&2
fi

# 4. Install the /artifact reopen skill
SKILL_DST="$HOME/.claude/skills/artifact"
echo "==> Installing /artifact skill to $SKILL_DST"
mkdir -p "$SKILL_DST"
cp "$REPO_DIR/skill/SKILL.md" "$SKILL_DST/SKILL.md"

echo ""
echo "✅ Done. Now RESTART Claude Code, then in any session say:"
echo "     把这个结果做成 artifact 发布   /   \"make this into an artifact\""
echo "   Reopen anytime with: /artifact"
echo "   Server will run at: http://localhost:${ARTIFACTS_PORT:-7891}"
