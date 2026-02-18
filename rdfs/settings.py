import os
from pathlib import Path
import environ

# ======================================================
# BASE DIRECTORY
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ======================================================
# ENVIRONMENT VARIABLES
# ======================================================
env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

ENVIRONMENT = env('ENVIRONMENT', default='development')
IS_PRODUCTION = ENVIRONMENT == 'production'
USE_REDIS_CHANNEL_LAYER = env.bool('USE_REDIS_CHANNEL_LAYER', default=False)

# ======================================================
# SECURITY
# ======================================================
SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)

# ======================================================
# ALLOWED HOSTS
# ======================================================
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost'])

# Add wildcard for development only
if DEBUG:
    ALLOWED_HOSTS.append('*')

# Auto-detect Render.com deployment
RENDER_EXTERNAL_HOSTNAME = env('RENDER_EXTERNAL_HOSTNAME', default=None)
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# ======================================================
# INSTALLED APPS
# ======================================================
INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Channels
    'channels',

    # Project apps
    'accounts',
    'main',
    'terminal',
    'vehicles',
    'reports',
    
    # Cloudinary
    'cloudinary',
    'cloudinary_storage',
]

# ======================================================
# MIDDLEWARE
# ======================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'accounts.middleware.SessionSecurityMiddleware',
]

# ======================================================
# URLS / WSGI
# ======================================================
ROOT_URLCONF = 'rdfs.urls'
WSGI_APPLICATION = 'rdfs.wsgi.application'

# ======================================================
# TEMPLATES
# ======================================================
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
            ],
        },
    },
]

# ======================================================
# DATABASE
# ======================================================
# Production PostgreSQL
DATABASES = {
    'default': env.db('DATABASE_URL', default='postgresql://postgres:admin@localhost:5432/rdfs_db')
}

# Local SQLite3 (commented out)
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# ======================================================
# AUTH / USERS
# ======================================================
AUTH_USER_MODEL = 'accounts.CustomUser'
AUTH_PASSWORD_VALIDATORS = []

LOGIN_URL = '/accounts/terminal-access/'
LOGIN_REDIRECT_URL = '/dashboard/staff/'
LOGOUT_REDIRECT_URL = '/passenger/public_queue/'

# ======================================================
# INTERNATIONALIZATION
# ======================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

# ======================================================
# STATIC FILES (WHITENOISE)
# ======================================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# ======================================================
# MEDIA FILE STORAGE
# ======================================================
# Cloudinary Configuration
CLOUDINARY_URL = env('CLOUDINARY_URL', default='')
if CLOUDINARY_URL:
    import re
    match = re.match(r'cloudinary://(\d+):([^@]+)@(.+)', CLOUDINARY_URL)
    if match:
        CLOUDINARY_STORAGE = {
            'CLOUD_NAME': match.group(3),
            'API_KEY': match.group(1),
            'API_SECRET': match.group(2),
        }
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Local media storage (commented out)
# DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
# MEDIA_URL = '/media/'
# MEDIA_ROOT = BASE_DIR / 'media'

# ======================================================
# DEFAULT PK
# ======================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ======================================================
# CHANNELS CONFIGURATION
# ======================================================
ASGI_APPLICATION = 'rdfs.asgi.application'

if USE_REDIS_CHANNEL_LAYER:
    REDIS_URL = env('REDIS_URL', default='redis://127.0.0.1:6379')
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# ======================================================
# SESSION / SECURITY
# ======================================================
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = env.int('SESSION_COOKIE_AGE', default=900)  # 15 minutes default
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=IS_PRODUCTION)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=IS_PRODUCTION)

# ======================================================
# PRODUCTION SECURITY
# ======================================================
if IS_PRODUCTION:
    DEBUG = False

    SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True)
    SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=True)
    
    # Additional security headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
