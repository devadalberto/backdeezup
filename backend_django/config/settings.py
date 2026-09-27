from pathlib import Path

import dj_database_url
from decouple import config, UndefinedValueError
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ── CRITICAL: SECRET_KEY must be explicitly set — no insecure default ─────────
try:
    SECRET_KEY = config('DJANGO_SECRET_KEY')
except UndefinedValueError:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY environment variable is not set. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(50))\""
    )

if SECRET_KEY in ('insecure-key', 'change-me', '', 'django-insecure'):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is set to a known insecure value.")

# ── DEBUG defaults to False — must be explicitly enabled ─────────────────────
DEBUG = config('DEBUG', cast=bool, default=False)

# ── ALLOWED_HOSTS defaults to localhost only ─────────────────────────────────
_allowed = config('ALLOWED_HOSTS', default='localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(',') if h.strip()]

# ── CORS: closed by default, explicit opt-in only ────────────────────────────
_cors = config('CORS_ALLOWED_ORIGINS', default='').strip()
if _cors == '*':
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = []
elif _cors:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = [h.strip() for h in _cors.split(',') if h.strip()]
else:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = []

# ── CSRF trusted origins ──────────────────────────────────────────────────────
_csrf = config('CSRF_TRUSTED_ORIGINS', default='').strip()
CSRF_TRUSTED_ORIGINS = [h.strip() for h in _csrf.split(',') if h.strip() and h.strip() != '*']

INSTALLED_APPS = [
    # Wagtail — must come before django.contrib.admin
    'wagtail.contrib.forms',
    'wagtail.contrib.redirects',
    'wagtail.embeds',
    'wagtail.sites',
    'wagtail.users',
    'wagtail.snippets',
    'wagtail.documents',
    'wagtail.images',
    'wagtail.search',
    'wagtail.admin',
    'wagtail',
    'modelcluster',
    'taggit',
    'wagtailmedia',

    # Django
    'django.contrib.postgres',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Project apps
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    'django_ratelimit',
    'django_htmx',
    'google_media_backup',
    'google_gmail_backup',
    'accounts',
    'core',
    'media_vault',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'wagtail.contrib.redirects.middleware.RedirectMiddleware',
]

# ── HTTPS security headers (production only) ─────────────────────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', cast=bool, default=False)
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', cast=int, default=0)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [
        BASE_DIR / 'templates',
        BASE_DIR / 'google_media_backup' / 'templates',
        BASE_DIR / 'google_gmail_backup' / 'templates',
    ],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'

# ── Database: PostgreSQL primary, SQLite for tests only ───────────────────────
DATABASE_URL = config('DATABASE_URL', default='')
if DATABASE_URL:
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'TEST': {'NAME': ':memory:'},
        }
    }

LANGUAGE_CODE = 'en-us'
TIME_ZONE = config('TIME_ZONE', default='America/Los_Angeles')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = config('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles'))
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = '/media/'
MEDIA_ROOT = config('MEDIA_ROOT', default=str(BASE_DIR / 'media'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Integrity check (Phase 31) — read-only re-hash sample, off switch below ───
INTEGRITY_CHECK_ENABLED = config('INTEGRITY_CHECK_ENABLED', cast=bool, default=True)
INTEGRITY_CHECK_SAMPLE_SIZE = config('INTEGRITY_CHECK_SAMPLE_SIZE', cast=int, default=200)

# ── Storage guard (Phase 32) — warn/pause thresholds, off switch below ────────
STORAGE_WARN_PCT = config('STORAGE_WARN_PCT', cast=int, default=85)
STORAGE_PAUSE_PCT = config('STORAGE_PAUSE_PCT', cast=int, default=95)
STORAGE_GUARD_ENABLED = config('STORAGE_GUARD_ENABLED', cast=bool, default=True)

# ── Notifications (Phase 33) — every channel off unless its env var is set ────
NOTIFY_WEBHOOK_URL = config('NOTIFY_WEBHOOK_URL', default='')
NOTIFY_SLACK_URL = config('NOTIFY_SLACK_URL', default='')
NOTIFY_DISCORD_URL = config('NOTIFY_DISCORD_URL', default='')
NOTIFY_EMAIL_TO = config('NOTIFY_EMAIL_TO', default='')
# Hours without a successful RunLog before the stale-backup Beat check fires. 0 disables it.
NOTIFY_STALE_BACKUP_HOURS = config('NOTIFY_STALE_BACKUP_HOURS', cast=int, default=0)

# ── SMTP (only used if NOTIFY_EMAIL_TO is set) ────────────────────────────────
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', cast=int, default=587)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool, default=True)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='backdeezup@localhost')

# ── Cleanup safeguards (Phase 34) ──────────────────────────────────────────────
# Global pause: skips every REAL cleanup run (run-all, Beat, make cleanup-run,
# the Execute API) with a log line. Dry runs are unaffected.
CLEANUP_PAUSED = config('CLEANUP_PAUSED', cast=bool, default=False)
# Dry-run-required + exact-count confirm — applies ONLY to the Execute UI path,
# not to run_all_enabled_rules / make cleanup-run / Beat (see services_rules.py).
CLEANUP_REQUIRE_DRY_RUN = config('CLEANUP_REQUIRE_DRY_RUN', cast=bool, default=True)
CLEANUP_DRY_RUN_MAX_AGE_HOURS = config('CLEANUP_DRY_RUN_MAX_AGE_HOURS', cast=int, default=24)

# ── Export to ZIP/TAR (Phase 36) ───────────────────────────────────────────────
# Above this many resolved items, /dashboard/export/ runs as a Celery task
# writing to MEDIA_ROOT/exports/ instead of streaming synchronously.
# scope=everything always goes async regardless of count.
EXPORT_ASYNC_THRESHOLD = config('EXPORT_ASYNC_THRESHOLD', cast=int, default=200)

# ── Restore to local dir (Phase 37) ────────────────────────────────────────────
# Every restore is written inside this root -- core.restore rejects any
# destination that resolves outside it (path traversal guard).
RESTORE_ROOT = config('RESTORE_ROOT', default=str(Path(MEDIA_ROOT) / 'restores'))
# "Can I restore a file?" weekly Beat check -- off by default (dashboard button
# always works regardless of this flag; this only controls the scheduled run).
RESTORE_SMOKE_TEST_ENABLED = config('RESTORE_SMOKE_TEST_ENABLED', cast=bool, default=False)

# ── PostgreSQL backup (Phase 38) ────────────────────────────────────────────────
# `make db-backup` / `make db-restore` always work (pg_dump/pg_restore run inside
# the `db` container). This block only gates the OPTIONAL Celery Beat task that
# also takes a dump (via pg_dump against DATABASE_URL) and prunes old ones -- off
# by default. Both write into the same directory, bind-mounted at DB_BACKUP_DIR.
DB_BACKUP_ENABLED = config('DB_BACKUP_ENABLED', cast=bool, default=False)
DB_BACKUP_KEEP_LAST = config('DB_BACKUP_KEEP_LAST', cast=int, default=14)
DB_BACKUP_DIR = config('DB_BACKUP_DIR', default='/app/backups')

# ── Structured logging ────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'console',
        },
    },
    'loggers': {
        'google_gmail_backup': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'google_media_backup': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'media_vault':         {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django.security':     {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
}

ADMIN_SITE_HEADER = config('ADMIN_SITE_HEADER', default='BackDeezUp Admin')
ADMIN_SITE_TITLE  = config('ADMIN_SITE_TITLE',  default='BackDeezUp')
ADMIN_INDEX_TITLE = config('ADMIN_INDEX_TITLE', default='Dashboard')

SWAGGER_TITLE       = config('SWAGGER_TITLE',       default='BackDeezUp API')
SWAGGER_DESCRIPTION = config('SWAGGER_DESCRIPTION', default='')
SWAGGER_VERSION     = config('SWAGGER_VERSION',     default='0.1.0')

# ── Wagtail ───────────────────────────────────────────────────────────────────
WAGTAIL_SITE_NAME      = config('WAGTAIL_SITE_NAME',      default='BackDeezUp Media Vault')
WAGTAILADMIN_BASE_URL  = config('WAGTAILADMIN_BASE_URL',  default='http://localhost:8844')
WAGTAILIMAGES_IMAGE_MODEL  = 'media_vault.VaultImage'
WAGTAILDOCS_DOCUMENT_MODEL = 'media_vault.VaultDocument'
WAGTAILMEDIA_MEDIA_MODEL   = 'media_vault.VaultMedia'
WAGTAILIMAGES_MAX_UPLOAD_SIZE = 1024 * 1024 * 1024
WAGTAILMEDIA_MAX_UPLOAD_SIZE  = 256 * 1024 * 1024 * 1024
WAGTAIL_ENABLE_UPDATE_CHECK = False
WAGTAILSEARCH_BACKENDS = {"default": {"BACKEND": "wagtail.search.backends.database"}}

# ── Custom User Model ────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.BackupUser'

# ── Pydantic v2 project-wide ──────────────────────────────────────────────────
# Schemas in backend_django/schemas.py — use model_validate() in all views.

# ── Cache (Redis) ─────────────────────────────────────────────────────────────
REDIS_URL = config('REDIS_URL', default='redis://redis:6379/0')
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"socket_connect_timeout": 2},
        "KEY_PREFIX": "backdeezup",
    }
}
RATELIMIT_USE_CACHE = "default"

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL              = config('REDIS_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND          = 'django-db'
CELERY_RESULT_EXTENDED         = True
CELERY_BEAT_SCHEDULER          = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_SERIALIZER         = 'json'
CELERY_RESULT_SERIALIZER       = 'json'
CELERY_ACCEPT_CONTENT          = ['json']
CELERY_TIMEZONE                = 'America/Los_Angeles'
CELERY_TASK_TRACK_STARTED      = True
CELERY_TASK_TIME_LIMIT         = 3600        # 1h hard limit per task
CELERY_TASK_SOFT_TIME_LIMIT    = 3300        # 55min soft limit (raises SoftTimeLimitExceeded)
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50       # recycle workers to prevent memory leaks

# ── Sentry ────────────────────────────────────────────────────────────────────
_sentry_dsn = config('SENTRY_DSN', default='')
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    import logging as _logging

    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=config('SENTRY_ENVIRONMENT', default='production'),
        release=config('SENTRY_RELEASE', default=''),
        integrations=[
            DjangoIntegration(transaction_style='url'),
            CeleryIntegration(monitor_beat_tasks=True),
            RedisIntegration(),
            LoggingIntegration(level=_logging.INFO, event_level=_logging.ERROR),
        ],
        traces_sample_rate=0.1,      # 10% of requests traced (adjust as needed)
        profiles_sample_rate=0.05,   # 5% profiled
        send_default_pii=False,      # never send PII (emails, names) to Sentry
    )

SILENCED_SYSTEM_CHECKS = ["django_ratelimit.W001"]
