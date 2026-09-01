#!/usr/bin/env bash
# Gate 5, the half that needs Docker on the Mac.
#
# Runs only SAFE, non-destructive steps: the addon tests, a fresh backup, and
# a checksum verification. It deliberately does NOT run the isolated restore
# drill, because that ends in `docker compose down -v` and should stay in a
# human's hands. Follow docs/RESTORE-DRILL.md for that.
#
# Usage:  ./scripts/gate5-checks.sh
# Writes: backups/gate5-checks-<UTC timestamp>.log

set -uo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
log="backups/gate5-checks-${ts}.log"
mkdir -p backups

{
  echo "GGD Gate 5 checks — ${ts}"
  echo "======================================================================"

  echo
  echo "### 0. Environment"
  docker compose ps || echo "RESULT: docker compose ps FAILED"
  df -h . | tail -1

  echo
  echo "### 1. Addon tests (expect 108 passing)"
  if ./scripts/run-addon-tests.sh; then
    echo "RESULT: addon tests EXIT 0"
  else
    echo "RESULT: addon tests FAILED (exit $?)"
  fi

  echo
  echo "### 2. Static validation"
  if ./scripts/validate-project.sh; then
    echo "RESULT: validate-project.sh EXIT 0"
  else
    echo "RESULT: validate-project.sh FAILED (exit $?)"
  fi

  echo
  echo "### 3. Fresh backup"
  if ./scripts/backup.sh; then
    echo "RESULT: backup EXIT 0"
  else
    echo "RESULT: backup FAILED (exit $?)"
  fi

  newest="$(ls -t backups | grep -E '^[0-9]{8}T[0-9]{6}Z$' | head -1 || true)"
  echo "NEWEST BACKUP: ${newest:-none}"
  if [ -n "${newest:-}" ]; then
    ls -lh "backups/${newest}"
    echo
    echo "### 4. Checksum verification"
    if ( cd "backups/${newest}" && { shasum -a 256 -c SHA256SUMS 2>/dev/null || sha256sum -c SHA256SUMS; } ); then
      echo "RESULT: checksums OK"
    else
      echo "RESULT: checksums FAILED"
    fi
  fi

  echo
  echo "======================================================================"
  echo "Done. Next: the isolated restore drill in docs/RESTORE-DRILL.md."
} 2>&1 | tee "$log"

echo
echo "Log written to: $log"
