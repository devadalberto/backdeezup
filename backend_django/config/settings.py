import os
from pathlib import Path
from decouple import config
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('DJANGO_SECRET_KEY', default='insecure-key')
DEBUG = config('DEBUG', cast=bool, default=False)
ALLOWED_HOSTS = [h.strip() for h in config('ALLOWED_HOSTS', default='*').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin','django.contrib.auth','django.contrib.contenttypes',
    'django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles',
    'google_media_backup',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'google_media_backup' / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'

DATABASE_URL = config('DATABASE_URL', default='')
if DATABASE_URL:
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}

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

ADMIN_SITE_HEADER = config('ADMIN_SITE_HEADER', default='Admin')
ADMIN_SITE_TITLE = config('ADMIN_SITE_TITLE', default='Admin')
ADMIN_INDEX_TITLE = config('ADMIN_INDEX_TITLE', default='Dashboard')

SWAGGER_TITLE = config('SWAGGER_TITLE', default='API')
SWAGGER_DESCRIPTION = config('SWAGGER_DESCRIPTION', default='')
SWAGGER_VERSION = config('SWAGGER_VERSION', default='0.1.0')
