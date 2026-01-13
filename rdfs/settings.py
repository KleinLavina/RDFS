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

# ======================================================
# SECURITY
# ======================================================
SECRET_KEY = env('SECRET_KEY', default='replace-this-with-your-own-secret-key')
DEBUG = env.bool('DEBUG', default=True)

# ======================================================
# ALLOWED HOSTS
# ======================================================
ALLOWED_HOSTS = [
    '*',
    '127.0.0.1',
    'localhost',
]

extra_hosts = env.list('ALLOWED_HOSTS', default=[])
for host in extra_hosts:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

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
if env('DATABASE_URL', default=None):
    DATABASES = {
        'default': env.db(),
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'rdfs_db',
            'USER': 'postgres',
            'PASSWORD': 'admin',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }

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
# MEDIA FILE STORAGE (Cloudinary)
# ======================================================
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': env('CLOUDINARY_CLOUD_NAME', default=''),
    'API_KEY': env('CLOUDINARY_API_KEY', default=''),
    'API_SECRET': env('CLOUDINARY_API_SECRET', default=''),
}

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# ======================================================
# DEFAULT PK
# ======================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ======================================================
# CHANNELS CONFIGURATION
# ======================================================
ASGI_APPLICATION = 'rdfs.asgi.application'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}

# ======================================================
# SESSION / SECURITY
# ======================================================
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 900
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# ======================================================
# PRODUCTION SECURITY
# ======================================================
if IS_PRODUCTION:
    DEBUG = False

    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
