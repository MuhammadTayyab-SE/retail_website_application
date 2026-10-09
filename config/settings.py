"""Minimal local foundation; no implicit credentials or database fallbacks."""

import os

from config.environment import configuration

_configuration = configuration(os.environ)
SECRET_KEY = _configuration["SECRET_KEY"]
DEBUG = _configuration["DEBUG"]
ALLOWED_HOSTS = _configuration["ALLOWED_HOSTS"]
DATABASES = _configuration["DATABASES"]
INSTALLED_APPS = []
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
