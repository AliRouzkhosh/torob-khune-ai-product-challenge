from pathlib import Path
import os
import secrets

BASE_DIR = Path(__file__).resolve().parent.parent
# Ephemeral development key; set DJANGO_SECRET_KEY for stable local sessions.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or secrets.token_urlsafe(50)
# Development only. This repository does not include a deployment configuration.
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.staticfiles', 'finder']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'finder.views.brand']}}]
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
LANGUAGE_CODE = 'fa'
TIME_ZONE = 'Asia/Tehran'
USE_TZ = True
STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AI_PROVIDER = 'mock'
BRAND_NAME = 'ترب‌خونه'
GITHUB_URL = os.environ.get('GITHUB_URL', '')
DATA_MODE = os.environ.get('DATA_MODE', 'real')
if DATA_MODE not in ('synthetic', 'real'):
    raise ValueError('DATA_MODE must be synthetic or real')
# Rank the bounded imported dataset; render only this many cards per response.
RESULT_DISPLAY_LIMIT = 60

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/browse/'
# One-click authentication is intentionally local-demo-only and can be disabled.
ENABLE_DEMO_LOGIN = DEBUG and os.environ.get('ENABLE_DEMO_LOGIN', '1') == '1'
DEMO_USERNAME = 'khane-demo'
DEMO_BALE_URL = os.environ.get('DEMO_BALE_URL', '')
