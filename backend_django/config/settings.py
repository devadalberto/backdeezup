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
    'django_apscheduler',
    'django_ratelimit',
    'google_media_backup',
    'google_gmail_backup',
    'accounts',
    'media_vault',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
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
TIME_ZONE = 'America/Los_Angeles'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = config('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles'))
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = '/media/'
MEDIA_ROOT = config('MEDIA_ROOT', default=str(BASE_DIR / 'media'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

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

# ── APScheduler ───────────────────────────────────────────────────────────────
BACKDEEZUP_SCHEDULER = config('BACKDEEZUP_SCHEDULER', cast=bool, default=False)
