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
  # db_name is what makes the scheduler work. Without it the cron thread has
  # no database to act on and every ir.cron silently never fires - including
  # Mail: Fetchmail Service, so incoming mail is never collected. Found on
  # 1 September 2026: every active cron's nextcall was hours to weeks stale.
  printf 'db_name = %s\n' "$ODOO_DB_NAME"
  # The address Odoo falls back to when the message author is not someone the
  # mail server will send as. Zoho accepts only kaan@germanygrowthdesk.com, so
  # a notification about an incoming email - which Odoo stamps with the
  # external sender's address - matched no server, fell back to localhost:25
  # and died with "111 Connection refused". Every such failure raised an
  # "Email Failure" notification while the mail that mattered went out fine.
  # Found 4 September 2026.
  printf 'email_from = %s\n' "${ODOO_NOTIFICATIONS_EMAIL:-kaan@germanygrowthdesk.com}"
  printf 'from_filter = %s\n' "${ODOO_NOTIFICATIONS_EMAIL:-kaan@germanygrowthdesk.com}"
} > "$config_path"

exec odoo server --config="$config_path"
