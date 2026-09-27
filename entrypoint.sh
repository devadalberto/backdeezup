#!/bin/bash
set -e

echo "[entrypoint] Checking media directory is writable..."
python -c "
import os
import sys

sys.path.insert(0, os.getcwd())
from core.errors import humanize_error

media_root = os.environ.get('MEDIA_ROOT', '/app/media')
probe = os.path.join(media_root, '.write_test')
try:
    os.makedirs(media_root, exist_ok=True)
    with open(probe, 'w') as fh:
        fh.write('ok')
    os.remove(probe)
except OSError as exc:
    err = humanize_error(exc)
    print(f\"[entrypoint] {err['title']}: {err['hint']}\", file=sys.stderr)
    print(
        '[entrypoint] Phase 41 note: on an existing install upgrading to the '
        \"non-root image, run 'make fix-perms' once, then retry.\",
        file=sys.stderr,
    )
    sys.exit(1)
"

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
