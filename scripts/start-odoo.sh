#!/usr/bin/env bash
set -euo pipefail

config_path="/tmp/ggd-odoo.conf"

umask 077
{
  printf '[options]\n'
  printf 'addons_path = /mnt/extra-addons\n'
  printf 'data_dir = /var/lib/odoo\n'
  printf 'admin_passwd = %s\n' "$ODOO_MASTER_PASSWORD"
  printf 'db_host = %s\n' "$HOST"
  printf 'db_port = %s\n' "$PORT"
  printf 'db_user = %s\n' "$USER"
  printf 'db_password = %s\n' "$PASSWORD"
  printf 'dbfilter = ^%s$\n' "$ODOO_DB_NAME"
} > "$config_path"

exec odoo server --config="$config_path"
