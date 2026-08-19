#!/bin/bash
# Run GGD CRM addon tests inside the Odoo container
# Usage: ./scripts/run-addon-tests.sh

set -e

echo "Running GGD CRM addon tests..."
echo "========================================"

docker compose exec -T odoo odoo -d ggd --test-enable \
  --test-tags /ggd_crm \
  --stop-after-init \
  -u ggd_crm

echo ""
echo "Test run complete!"
echo "If all 19 tests passed, the addon is ready."
