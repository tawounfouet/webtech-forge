from .base import *  # noqa: F401, F403
import environ

env = environ.Env()

DEBUG = False

CORS_ALLOWED_ORIGINS: list[str] = env.list("CORS_ALLOWED_ORIGINS", default=[])

# HTTPS enforcement
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# Logging niveau INFO en prod (pas DEBUG)
LOGGING["root"]["level"] = "INFO"  # noqa: F405
