"""
Django settings for henra project.
"""

import os
import sys
from pathlib import Path
from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

def _cast_bool(val):
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ('true', '1', 'yes', 'on', 't')

VERCEL = config('VERCEL', default=False, cast=_cast_bool)
DEBUG = config('DEBUG', default=not VERCEL, cast=_cast_bool)
VERCEL_URL = config('VERCEL_URL', default='').strip()
if VERCEL_URL.startswith(('https://', 'http://')):
    VERCEL_URL = VERCEL_URL.split('://', 1)[1].split('/', 1)[0]

CLOUDINARY_URL = config('CLOUDINARY_URL', default='')

if VERCEL and not CLOUDINARY_URL:
    raise ImproperlyConfigured(
        'CLOUDINARY_URL wajib dikonfigurasi agar upload media di Vercel tersimpan permanen.'
    )

if CLOUDINARY_URL:
    os.environ.setdefault('CLOUDINARY_URL', CLOUDINARY_URL)
    CLOUDINARY_STORAGE = {'PREFIX': ''}

SECRET_KEY = config('SECRET_KEY', default='')

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-local-development-only'
    else:
        raise ImproperlyConfigured(
            'SECRET_KEY wajib diatur untuk production.'
        )

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1' if DEBUG else '',
    cast=Csv(),
)
if VERCEL_URL and VERCEL_URL not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(VERCEL_URL)
if not DEBUG and (not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS):
    raise ImproperlyConfigured(
        'ALLOWED_HOSTS production harus berisi hostname yang eksplisit.'
    )

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='',
    cast=Csv(),
)
if VERCEL_URL:
    vercel_origin = f'https://{VERCEL_URL}'
    if vercel_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(vercel_origin)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = config(
    'SECURE_SSL_REDIRECT',
    default=not DEBUG,
    cast=_cast_bool,
)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'store',
    'dashboard',
    'accounts.apps.AccountsConfig',
]

if CLOUDINARY_URL:
    INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']

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

ROOT_URLCONF = 'henra.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'store.context_processors.cart_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'henra.wsgi.application'


# Database configuration
# Default to SQLite so the app and admin run immediately with all existing data.
# Set DB_ENGINE=mysql in .env when you want to use MySQL.
# Database configuration
DB_ENGINE = config('DB_ENGINE', default='sqlite3').lower()
if VERCEL and DB_ENGINE != 'mysql':
    raise ImproperlyConfigured(
        'DB_ENGINE=mysql wajib dikonfigurasi di Vercel untuk menggunakan TiDB.'
    )

if DB_ENGINE == 'mysql':
    DB_SSL_CA = Path(config(
        'DB_SSL_CA',
        default=str(BASE_DIR / 'certs' / 'isrgrootx1.pem'),
    ))

    if not DB_SSL_CA.is_file():
        raise ImproperlyConfigured(
            f'SSL certificate tidak ditemukan: {DB_SSL_CA}'
        )

    MYSQL_OPTIONS = {
        'charset': 'utf8mb4',
        'ssl_ca': str(DB_SSL_CA),
        'ssl_verify_cert': True,
        'ssl_verify_identity': True,
        'connect_timeout': config(
            'DB_CONNECT_TIMEOUT', default=20, cast=int
        ),
        'read_timeout': config(
            'DB_READ_TIMEOUT', default=30, cast=int
        ),
        'write_timeout': config(
            'DB_WRITE_TIMEOUT', default=30, cast=int
        ),
    }

    if sys.platform == 'win32':
        MYSQL_OPTIONS['bind_address'] = '0.0.0.0'

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('DB_NAME', default='hendra_sport'),
            'USER': config('DB_USER', default='root'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='127.0.0.1'),
            'PORT': config('DB_PORT', default='3306'),
            'CONN_MAX_AGE': 0,
            'OPTIONS': MYSQL_OPTIONS,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'id'

TIME_ZONE = 'Asia/Jakarta'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STORAGES = {
    'default': {
        'BACKEND': (
            'cloudinary_storage.storage.MediaCloudinaryStorage'
            if CLOUDINARY_URL
            else 'django.core.files.storage.FileSystemStorage'
        ),
    },
    'staticfiles': {
        'BACKEND': (
            'whitenoise.storage.CompressedManifestStaticFilesStorage'
            if VERCEL
            else 'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}
PAYMENT_PROOF_ROOT = config(
    'PAYMENT_PROOF_ROOT',
    default=str(BASE_DIR / 'private_uploads'),
)

# Flat fee added when a cart line includes custom name and number printing.
SABLON_FEE = 20000

# Payment credentials are intentionally sandbox-only; no production endpoint is used.
MIDTRANS_SANDBOX = True
MIDTRANS_SERVER_KEY = config('MIDTRANS_SERVER_KEY', default='')
MIDTRANS_CLIENT_KEY = config('MIDTRANS_CLIENT_KEY', default='')

BANK_TRANSFER_NAME = config('BANK_TRANSFER_NAME', default='')
BANK_TRANSFER_ACCOUNT_NAME = config('BANK_TRANSFER_ACCOUNT_NAME', default='')
BANK_TRANSFER_ACCOUNT_NUMBER = config('BANK_TRANSFER_ACCOUNT_NUMBER', default='')

SHIPPING_RATE_REGULAR = config('SHIPPING_RATE_REGULAR', default=18000, cast=int)
SHIPPING_RATE_EXPRESS = config('SHIPPING_RATE_EXPRESS', default=30000, cast=int)
CHECKOUT_SHIPPING_OPTIONS = (
    ('regular', 'Reguler (2–4 hari kerja)', SHIPPING_RATE_REGULAR),
    ('express', 'Express (1–2 hari kerja)', SHIPPING_RATE_EXPRESS),
)
if SHIPPING_RATE_REGULAR < 0 or SHIPPING_RATE_EXPRESS < 0:
    raise ImproperlyConfigured('Checkout shipping rates cannot be negative.')

LOGIN_URL = 'store:login'
LOGIN_REDIRECT_URL = 'store:home'
LOGOUT_REDIRECT_URL = 'store:login'

EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=_cast_bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=_cast_bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)

TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_FROM_NUMBER = config('TWILIO_FROM_NUMBER', default='')

EMAIL_VERIFICATION_MAX_AGE = 24 * 60 * 60
PHONE_VERIFICATION_MAX_AGE = 10 * 60

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
