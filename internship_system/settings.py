"""
Django settings for internship_system project.
"""

import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── SECURITY ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-this-before-production-xyz123!')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = ['*']   # Render's own domain is always trusted; tighten later if you want

CSRF_TRUSTED_ORIGINS = [
    'https://YOUR-APP-NAME.onrender.com',   # replace with your actual Render URL
]

# ─── APPLICATIONS ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Project apps
    'accounts',
    'placements',
    'logbook',
    'assessment',
    'announcements',
    'reports',
    'notifications',
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

ROOT_URLCONF = 'internship_system.urls'

# ─── TEMPLATES ────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.sidebar_badges',
            ],
        },
    },
]

WSGI_APPLICATION = 'internship_system.wsgi.application'

# ─── DATABASE ─────────────────────────────────────────────────────────────────
# Reads DATABASE_URL if set (Render production) — otherwise falls back to
# local SQLite, so nothing changes for local development on your own machine.
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# ─── AUTH ─────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.CustomUser'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/accounts/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── LOCALISATION ─────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

# ─── STATIC & MEDIA ───────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── FILE UPLOAD CONSTRAINTS ──────────────────────────────────────────────────
CV_ALLOWED_EXTENSIONS = ['pdf', 'docx']
CV_MAX_SIZE_MB = 2
CV_MAX_SIZE_BYTES = CV_MAX_SIZE_MB * 1024 * 1024

LOGBOOK_ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'docx']
LOGBOOK_MAX_SIZE_MB = 5
LOGBOOK_MAX_SIZE_BYTES = LOGBOOK_MAX_SIZE_MB * 1024 * 1024

LOGBOOK_INACTIVE_DAYS = 5
LOGBOOK_BEHIND_DAYS   = 7

# ─── EMAIL (password reset) ───────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'InternTrack <noreply@interntrack.local>'