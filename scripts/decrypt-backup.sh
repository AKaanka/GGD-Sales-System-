#!/usr/bin/env bash
# Verify and decrypt an encrypted backup so the restore drill can run on it.
#
# Usage:
#   ./scripts/decrypt-backup.sh <backup-dir> <identity-file> [output-dir]
#
#   backup-dir     a directory of *.age files plus SHA256SUMS, local or on the
#                  external disk. This is what backup.sh writes.
#   identity-file  the age private key, from the password manager. Copy it in
#                  for the restore and delete it afterwards; it does not live
#                  on this machine.
#   output-dir     where to write the plaintext. Defaults to a temporary
#                  directory, printed at the end.
#
# The checksums cover the ciphertext, so the copy is verified before the key
# is used at all. A backup that fails this check should not be decrypted or
# trusted - fetch another copy instead.
#
# The output is a real, readable dump of the whole CRM. Delete it when the
# restore is done: it is exactly what the encryption exists to prevent.

set -euo pipefail

[ $# -ge 2 ] || { echo "usage: $0 <backup-dir> <identity-file> [output-dir]" >&2; exit 2; }

backup_dir="$1"
identity="$2"
out_dir="${3:-$(mktemp -d "${TMPDIR:-/tmp}/ggd-restore.XXXXXX")}"

[ -d "$backup_dir" ]  || { echo "ABORT: no such backup directory: $backup_dir" >&2; exit 1; }
[ -r "$identity" ]    || { echo "ABORT: cannot read the identity file: $identity" >&2; exit 1; }
command -v age >/dev/null 2>&1 || { echo "ABORT: age is not installed. brew install age" >&2; exit 1; }

shopt -s nullglob
encrypted=("$backup_dir"/*.age)
[ ${#encrypted[@]} -gt 0 ] || { echo "ABORT: no .age files in $backup_dir" >&2; exit 1; }

echo "### 1. Verify the copy before using the key"
if [ -f "$backup_dir/SHA256SUMS" ]; then
  if command -v shasum >/dev/null 2>&1; then
    (cd "$backup_dir" && shasum -a 256 -c SHA256SUMS) \
      || { echo "ABORT: checksum verification failed - do not trust this copy." >&2; exit 1; }
  fi
else
  echo "WARNING: no SHA256SUMS in $backup_dir; integrity was not verified." >&2
fi

echo ""
echo "### 2. Decrypt into $out_dir"
mkdir -p "$out_dir"
for f in "${encrypted[@]}"; do
  base="$(basename "$f" .age)"
  age --decrypt --identity "$identity" --output "${out_dir}/${base}" "$f"
  echo "  $base"
done

# Checksums over the plaintext, so the restore drill can verify as it always has.
if command -v shasum >/dev/null 2>&1; then
  (cd "$out_dir" && shasum -a 256 ./*.gz > SHA256SUMS)
elif command -v sha256sum >/dev/null 2>&1; then
  (cd "$out_dir" && sha256sum ./*.gz > SHA256SUMS)
fi
chmod -R go-rwx "$out_dir" 2>/dev/null || true

echo ""
echo "Decrypted to: $out_dir"
echo ""
echo "Run the drill against it:"
echo "    ./scripts/gate5-restore-drill.sh \"$out_dir\""
echo ""
echo "Delete it when you are done - it is an unencrypted copy of the whole CRM:"
echo "    rm -rf \"$out_dir\""
