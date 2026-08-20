#!/bin/bash
# Run GGD CRM addon tests inside the Odoo container
# Usage: ./scripts/run-addon-tests.sh

set -euo pipefail

echo "Running GGD CRM addon tests..."
echo "========================================"

# The test run reuses the configuration the normal Odoo service writes into the
# container. If it is not readable, the run below would fail deep inside Odoo
# with a confusing traceback, so check for it first. Only the readability of
# the path is tested; nothing from the file or the environment is printed.
if ! docker compose exec -T odoo /bin/bash -lc '[ -r /tmp/ggd-odoo.conf ]' >/dev/null 2>&1; then
  echo "ERROR: cannot read /tmp/ggd-odoo.conf inside the odoo container." >&2
  echo "Start the normal Odoo service first, then re-run this script." >&2
  exit 1
fi

docker compose exec -T odoo /bin/bash -lc '
  exec odoo server \
    --config=/tmp/ggd-odoo.conf \
    --http-interface=127.0.0.1 \
    --http-port=8071 \
    --gevent-port=8072 \
    -d "$ODOO_DB_NAME" \
    --test-enable \
    --test-tags /ggd_crm \
    --stop-after-init \
    -u ggd_crm
'

echo ""
echo "Test run complete!"
echo "Confirm the Odoo result reports 0 failed and 0 errors."
