# 18 — Sécurité

> **ADR de référence :** ADR-008, ADR-010, ADR-015
> **Dépendances :** 03-backend-django.md, 05-api-drf.md

---

## Django Deployment Checklist

```python
# config/settings/production.py
from .base import *

DEBUG = False
SECRET_KEY = env("SECRET_KEY")  # min 50 chars, aléatoire
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# HTTPS
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Cookies
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

# Clickjacking
X_FRAME_OPTIONS = "DENY"

# Content Security Policy (via django-csp)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # à restreindre si possible
CSP_IMG_SRC = ("'self'", "data:")

# Email erreurs
ADMINS = [("WebTech Ops", env("ADMIN_EMAIL", default="ops@webtech.fr"))]
SERVER_EMAIL = "forge-errors@webtech.fr"
```

---

## OWASP API Security Top 10 — Mesures par risque

| Risque OWASP | Mesure WebTech Forge |
|---|---|
| **API1 — BOLA** (accès objet non autorisé) | `has_object_permission` sur chaque ViewSet + workspace scoping systématique |
| **API2 — Authentification cassée** | JWT + refresh tokens + MFA TOTP obligatoire pour Admin/Owner |
| **API3 — Propriétés exposées en excès** | Sérializers explicites (jamais `fields = "__all__"`) |
| **API4 — Consommation non bornée** | Throttling 300 req/min + pagination obligatoire (max 100 items) |
| **API5 — BFLA** (accès fonction non autorisé) | Permissions par rôle sur chaque action (deploy, rollback, endorse) |
| **API6 — SSRF** | Validation des URLs de dépôts Git contre une whitelist de domaines autorisés |
| **API7 — Mauvaise configuration** | Django deployment checklist + Traefik middlewares sécurité |
| **API8 — Injection** | ORM Django (paramétré par défaut) + validation stricte des inputs |
| **API9 — Inventory management** | OpenAPI généré + versioning d'API (`/api/v1/`) |
| **API10 — Unsafe consumption** | Validation HMAC des webhooks GitHub + timeout sur toutes les requêtes externes |

---

## Contrôle d'accès au socket Docker

Le socket Docker donne un accès quasi-root à l'hôte. Mesures obligatoires :

```yaml
# Seul le service celery-worker a accès au socket, en lecture-écriture
celery-worker:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  security_opt:
    - no-new-privileges:true
  cap_drop:
    - ALL
  read_only: true
  tmpfs:
    - /tmp
```

Règles dans le DockerAdapter :
- Aucun montage de `/var/run/docker.sock` dans les conteneurs applicatifs des workspaces.
- Refus des images avec `USER root` non justifié (scan Trivy en V2).
- Aucune option `--privileged` dans `containers.run()`.
- Journalisation de chaque appel Docker dans l'AuditLog.

---

## MFA TOTP

```python
# apps/accounts/views.py
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class MFAVerifyView(APIView):
    def post(self, request):
        token = request.data.get("token")
        device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
        if not device:
            return Response({"error": "MFA not configured"}, status=status.HTTP_400_BAD_REQUEST)
        if device.verify_token(token):
            # Marquer la session MFA comme vérifiée
            request.session["mfa_verified"] = True
            return Response({"ok": True})
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)


class MFASetupView(APIView):
    def post(self, request):
        device, created = TOTPDevice.objects.get_or_create(
            user=request.user,
            defaults={"name": "Authenticator App"},
        )
        return Response({
            "provisioning_uri": device.config_url,
            "secret": device.key,
        })
```

---

## Validation des URLs de dépôts Git

Éviter les SSRF via des URLs Git pointant vers des ressources internes :

```python
# adapters/git_adapter.py
import re
from django.conf import settings

ALLOWED_GIT_HOSTS = getattr(settings, "ALLOWED_GIT_HOSTS", [
    "github.com",
    "gitlab.com",
    "bitbucket.org",
])


def validate_repo_url(url: str) -> None:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "ssh"):
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")
    if parsed.hostname not in ALLOWED_GIT_HOSTS:
        raise ValueError(f"Git host not allowed: {parsed.hostname}. Allowed: {ALLOWED_GIT_HOSTS}")
    # Bloquer les IPs privées
    import ipaddress
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        if ip.is_private or ip.is_loopback:
            raise ValueError("Private IP addresses not allowed in repo URLs")
    except ValueError:
        pass  # hostname string, pas une IP — OK
```

---

## Rétention et redaction des logs

```python
# apps/audit/utils.py
import re

SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|secret|token|key|api_key|auth)[=:\s]+\S+"),
    re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),  # base64-like secrets
]


def redact_sensitive(text: str) -> str:
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub(lambda m: m.group().split("=")[0] + "=***REDACTED***", text)
    return text
```

Tous les `DeploymentEvent.message` passent par `redact_sensitive()` avant insertion.

---

## Revue de sécurité périodique

| Action | Fréquence |
|---|---|
| Revue des membres et rôles Workspace | Trimestrielle |
| Rotation des secrets plateforme (`SECRET_KEY`, DB passwords, registry secret) | Annuelle ou après incident |
| Vérification des images Docker en production (Trivy) | Mensuelle (V2) |
| Test de pénétration API | Annuelle |
| Restore drill backup | Mensuelle |
| Revue des règles Activator (circuit-breaker, actions autorisées) | Trimestrielle |
