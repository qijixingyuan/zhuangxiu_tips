#!/usr/bin/env bash
set -euo pipefail

data_dir="/www/wwwroot/zhuangxiu-data"
backup_dir="${data_dir}/backups"
stamp="$(date +%F-%H%M%S)"
mkdir -p "${backup_dir}"

sqlite3 "${data_dir}/renovation.sqlite3" ".backup '${backup_dir}/renovation-${stamp}.sqlite3'"
tar -C "${data_dir}" -czf "${backup_dir}/uploads-${stamp}.tar.gz" uploads
find "${backup_dir}" -type f -mtime +30 -delete
