"""
Django settings for internship_system project.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── SECURITY ────────────────────────────────────────────────────────────────
SECRET_KEY = 'django-insecure-change-this-before-production-xyz123!'
DEBUG = True
ALLOWED_HOSTS = ['*']   # tighten in production

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
        # Global templates folder at project root
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
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ─── AUTH ─────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.CustomUser'   # swap in our custom user

# Where to go after login/logout
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
STATICFILES_DIRS = [BASE_DIR / 'static']   # dev static files
STATIC_ROOT = BASE_DIR / 'staticfiles'     # collectstatic output

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── FILE UPLOAD CONSTRAINTS ──────────────────────────────────────────────────
# Enforced in forms.py clean() methods — not Django built-ins
CV_ALLOWED_EXTENSIONS = ['pdf', 'docx']
CV_MAX_SIZE_MB = 2
CV_MAX_SIZE_BYTES = CV_MAX_SIZE_MB * 1024 * 1024   # 2 097 152 bytes

# Logbook attachments
LOGBOOK_ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'docx']
LOGBOOK_MAX_SIZE_MB = 5
LOGBOOK_MAX_SIZE_BYTES = LOGBOOK_MAX_SIZE_MB * 1024 * 1024   # 5 242 880 bytes

# Days without a log before student is flagged
LOGBOOK_INACTIVE_DAYS = 5    # supervisor alert
LOGBOOK_BEHIND_DAYS   = 7    # coordinator alert

# ─── EMAIL (password reset) ───────────────────────────────────────────────────
# Console backend: "sends" email by printing it straight to the terminal
# running `runserver` — no real mail server needed. Perfect for local dev
# and demos. Switch EMAIL_BACKEND to an SMTP one (Gmail, SendGrid, etc.)
# only when this needs to reach a real inbox.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'InternTrack <noreply@interntrack.local>'