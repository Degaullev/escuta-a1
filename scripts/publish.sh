#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Safety check: ensure .env is never tracked
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "ERROR: .env is tracked by git! Aborting." >&2
  exit 1
fi

git add -A
if git diff --cached --quiet; then
  echo "変更はありません（すでに最新が公開済みです）。"
  exit 0
fi

git commit -m "Update lessons and media ($(date '+%Y-%m-%d %H:%M'))"
git push origin main
echo "✅ GitHub Pages へ反映しました！（約30〜60秒で https://degaullev.github.io/escuta-a1/ に反映されます）"
