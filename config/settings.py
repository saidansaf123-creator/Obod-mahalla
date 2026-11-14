"""Obod mahalla — Django sozlamalari."""
from pathlib import Path

import environ
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["127.0.0.1", "localhost"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

# Серверда SECRET_KEY ўзгарувчисини албатта беринг; берилмаса — вақтинчалик тасодифий калит
SECRET_KEY = env("SECRET_KEY", default="") or get_random_secret_key()
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# Railway домени автоматик қўшилади
RAILWAY_DOMAIN = env("RAILWAY_PUBLIC_DOMAIN", default="")
if RAILWAY_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_DOMAIN}")
if env("RAILWAY_ENVIRONMENT", default=""):
    ALLOWED_HOSTS.append(".railway.app")
    ALLOWED_HOSTS.append(".up.railway.app")
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Loyiha ilovalari
    "apps.energy",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Hozircha SQLite; keyinroq .env dagi DATABASE_URL orqali PostgreSQL'ga o'tish mumkin
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Статик файлларни Django ўзи (whitenoise) сиқиб беради
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Сайт ичидаги админ панели пароли (Railway'да ADMIN_PANEL_PASSWORD орқали ўзгартириш мумкин)
ADMIN_PANEL_PASSWORD = env("ADMIN_PANEL_PASSWORD", default="6613")
SESSION_COOKIE_AGE = 60 * 60 * 12

# Excel va boshqa xom ma'lumotlar papkasi
DATA_DIR = BASE_DIR / "data"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
