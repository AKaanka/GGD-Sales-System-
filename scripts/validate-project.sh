#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

echo "Checking shell scripts..."
for script in scripts/*.sh; do
  bash -n "$script"
done

echo "Checking Python and XML files..."
python3 - <<'PY'
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path.cwd()

for path in sorted(root.rglob("*.py")):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

for path in sorted(root.rglob("*.xml")):
    ET.parse(path)
PY

echo "Running script unit tests..."
python3 -m unittest discover -s tests/scripts

echo "Running MCP connector unit tests..."
python3 -m unittest discover -s tests/mcp

if command -v node >/dev/null 2>&1; then
  echo "Checking n8n workflow exports..."
  node tests/workflows/test-workflow-exports.js
  echo "Checking legacy Workflow 4 matcher regressions..."
  node tests/workflow4/test-evaluate-reply-match.js
else
  echo "Node.js is unavailable; n8n workflow tests were skipped."
fi

if [[ -f .env ]]; then
  echo "A local .env exists. Confirming Git ignores it..."
  if git check-ignore --quiet .env 2>/dev/null; then
    echo ".env is ignored: OK"
  else
    echo "ERROR: .env exists but is not ignored by Git."
    exit 1
  fi
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    echo "ERROR: .env is tracked by Git. Remove it from Git before pushing."
    exit 1
  fi
  git diff --check
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "Checking Docker Compose configuration..."
  docker compose --env-file .env.example config --quiet
else
  echo "Docker is unavailable; Compose validation was skipped."
fi

echo "Project validation passed."
