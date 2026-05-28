from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INSTALLED_APPS += [  # noqa: F405
    "django_extensions",
]

# Désactiver les redirections HTTPS en dev
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
