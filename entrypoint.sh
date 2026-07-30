#!/bin/bash
set -e

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput

echo "[entrypoint] Syncing Wagtail site hostname..."
python manage.py shell -c "
from wagtail.models import Site
import os
# Use first entry of ALLOWED_HOSTS, fallback to localhost
hosts = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', 'localhost').split(',') if h.strip() and h.strip() not in ('*', 'localhost', '127.0.0.1')]
hostname = hosts[0] if hosts else 'localhost'
port = int(os.environ.get('WAGTAIL_SITE_PORT', '443'))
s, _ = Site.objects.get_or_create(is_default_site=True, defaults={'hostname': hostname, 'port': port, 'root_page_id': 1})
if s.hostname != hostname or s.port != port:
    s.hostname = hostname
    s.port = port
    s.save()
    print(f'[entrypoint] Site updated: {hostname}:{port}')
else:
    print(f'[entrypoint] Site OK: {hostname}:{port}')
"

echo "[entrypoint] Starting gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 300
