# WebTech Forge — Backend

Control plane Django 5.2 LTS du PaaS WebTech Forge.
Architecture : modulith DRF + Celery + Django Channels (WebSocket).

> **ADR de référence :** [ADR-002](../../docs/adr/ADR-002-modulith-django-drf.md) · [ADR-001](../../docs/adr/ADR-001-ontologie-organisation-workspace-project.md)

---

## Prérequis

| Outil | Version minimale |
|---|---|
| Python | 3.12 |
| PostgreSQL | 15 |
| Redis | 7 |
| Docker | 24 (pour les adapters) |

---

## Setup local

### 1. Créer l'environnement virtuel

```bash
python3.12 -m venv .venv
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate        # Windows
```

> Le dossier `.venv` est ignoré par git (`.gitignore`). Ne jamais le renommer.

### 2. Installer les dépendances

```bash
pip install -e ".[dev]"
```

Pour la prod uniquement (sans outils dev) :

```bash
pip install -e .
```

### 3. Configurer les variables d'environnement

```bash
cp .env.example .env
```

Éditer `.env` et renseigner au minimum :

```bash
# Générer une SECRET_KEY robuste
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Générer la clé de chiffrement des secrets workspace (AES-256 via Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Variables obligatoires dans `.env` :

| Variable | Description |
|---|---|
| `SECRET_KEY` | Clé Django (min. 50 chars, aléatoire) |
| `DATABASE_URL` | `postgres://user:pass@host:5432/dbname` |
| `REDIS_BROKER_URL` | `redis://localhost:6379/0` |
| `REDIS_CHANNELS_URL` | `redis://localhost:6379/1` |
| `FIELD_ENCRYPTION_KEY` | Clé Fernet pour `WorkspaceSecret.value` |

### 4. Démarrer PostgreSQL et Redis

Avec Docker (recommandé en dev) :

```bash
docker run -d --name forge-postgres \
  -e POSTGRES_DB=forge \
  -e POSTGRES_USER=forge \
  -e POSTGRES_PASSWORD=forge \
  -p 5432:5432 postgres:15-alpine

docker run -d --name forge-redis \
  -p 6379:6379 redis:7-alpine
```

Ou via le `docker-compose.platform.yml` complet (voir `docs/implementation/13-infrastructure-compose.md`).

### 5. Appliquer les migrations

```bash
python manage.py migrate
```

### 6. Créer un superutilisateur

```bash
python manage.py createsuperuser
# Email (= USERNAME_FIELD) + mot de passe demandés
```

### 7. Lancer le serveur de développement

```bash
# Serveur HTTP Django standard (sans WebSocket)
python manage.py runserver

# Serveur ASGI Daphne (HTTP + WebSocket)
daphne -p 8000 config.asgi:application
```

L'interface d'administration est disponible sur [http://localhost:8000/admin/](http://localhost:8000/admin/).

---

## Workers Celery

```bash
# Worker principal (queues deployments + activator)
celery -A config.celery worker -Q deployments,activator -l info

# Worker backups
celery -A config.celery worker -Q backups -l info

# Beat scheduler (tâches périodiques)
celery -A config.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Flower (monitoring Celery) :

```bash
pip install flower
celery -A config.celery flower --port=5555
# → http://localhost:5555
```

---

## Tests

```bash
# Lancer toute la suite
pytest

# Avec rapport de couverture HTML
pytest --cov=apps --cov-report=html
open htmlcov/index.html

# Tests d'un domaine spécifique
pytest tests/test_models/test_workspaces.py -v

# Tests rapides (sans couverture)
pytest -p no:cov -x
```

Cible de couverture V1 : **≥ 80 %** sur `apps/`.

---

## Qualité de code

```bash
# Vérification des types (mypy strict)
mypy apps/ adapters/

# Linting (ruff recommandé)
pip install ruff
ruff check apps/ adapters/
ruff format apps/ adapters/
```

---

## Architecture

```
src/backend/
├── config/
│   ├── settings/
│   │   ├── base.py          # Settings partagés
│   │   ├── development.py   # Override dev (DEBUG=True, CORS ouvert)
│   │   └── production.py    # Override prod (HTTPS, HSTS)
│   ├── urls.py              # Routes /api/v1/ + /admin/ + /metrics/
│   ├── asgi.py              # HTTP + WebSocket (Channels)
│   └── celery.py            # App Celery + task_routes + beat_schedule
│
├── apps/                    # Domaines métier (modulith)
│   ├── accounts/            # Custom User (email = login, MFA)
│   ├── organizations/       # Entité propriétaire / facturation
│   ├── workspaces/          # Frontière de sécurité principale + RBAC
│   ├── projects/            # Produit logique
│   ├── environments/        # dev / staging / preview / production
│   ├── services/            # Unité déployable (web, api, worker, cron…)
│   ├── deployments/         # Pipeline Medallion Bronze→Silver→Gold
│   ├── activator/           # Rules engine + circuit-breaker (V2)
│   ├── monitor/             # Monitor Hub — snapshots d'état
│   ├── catalog/             # Templates certifiés de services
│   └── audit/               # AuditLog + AuditMiddleware
│
└── adapters/                # Ports vers l'infrastructure
    ├── docker_adapter.py    # Docker SDK (run, build, healthcheck)
    ├── git_adapter.py       # Clone, SHA, message
    ├── traefik_adapter.py   # Labels Docker pour le routing
    ├── registry_adapter.py  # Registry local / Harbor
    ├── storage_adapter.py   # S3 (backups PostgreSQL + volumes)
    └── metrics_adapter.py   # Prometheus PromQL (Monitor Hub + Activator)
```

### Hiérarchie des objets métier

```
Organization → Workspace → Project → Environment → Service → Deployment
```

Le `Workspace` est la **frontière de sécurité** principale. Tous les querysets DRF filtrent par `workspace`.

### Communication inter-apps

Les apps Django communiquent via **imports Python directs** et **signaux Django** — jamais via HTTP ou message broker inter-process.

---

## API REST — Endpoints disponibles

Toutes les routes sont préfixées par `/api/v1/`. L'authentification est JWT Bearer (`Authorization: Bearer <token>`).
Le workspace courant est résolu depuis le header `X-Workspace-Slug` ou l'URL.

### Auth

| Méthode | URL | Description |
|---|---|---|
| `POST` | `/api/v1/auth/token/` | Obtenir access + refresh tokens |
| `POST` | `/api/v1/auth/token/refresh/` | Renouveler l'access token |
| `POST` | `/api/v1/auth/token/verify/` | Vérifier un token |

### Organizations

| Méthode | URL | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/organizations/` | Authentifié | Lister mes organisations |
| `POST` | `/api/v1/organizations/` | Authentifié | Créer une organisation |
| `GET/PUT/PATCH/DELETE` | `/api/v1/organizations/{slug}/` | Authentifié | CRUD organisation |

### Workspaces

| Méthode | URL | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/workspaces/` | Authentifié | Lister mes workspaces |
| `POST` | `/api/v1/workspaces/` | Authentifié | Créer un workspace |
| `GET/PUT/PATCH/DELETE` | `/api/v1/workspaces/{slug}/` | Authentifié | CRUD workspace |
| `GET/POST` | `/api/v1/workspaces/{slug}/members/` | Viewer+ / Admin | Membres |
| `DELETE` | `/api/v1/workspaces/{slug}/members/{id}/` | Admin | Supprimer membre |
| `GET/POST` | `/api/v1/workspaces/{slug}/secrets/` | Viewer+ | Secrets (valeur write-only) |
| `GET/PUT/PATCH` | `/api/v1/workspaces/{slug}/quota/` | Viewer+ / Admin | Quotas |

### Projects

| Méthode | URL | Permission | Description |
|---|---|---|---|
| `GET/POST` | `/api/v1/projects/` | Developer+ | CRUD projets |
| `GET/PUT/PATCH/DELETE` | `/api/v1/projects/{slug}/` | Developer+ | Détail projet |
| `GET/POST` | `/api/v1/projects/{slug}/repositories/` | Developer+ | Dépôts git |

### Environments

| Méthode | URL | Permission | Description |
|---|---|---|---|
| `GET/POST` | `/api/v1/environments/` | Developer+ | CRUD environments (`?project=<id>`) |
| `GET/PUT/PATCH/DELETE` | `/api/v1/environments/{id}/` | Developer+ | Détail + PromotionPolicy |

### Services

| Méthode | URL | Permission | Description |
|---|---|---|---|
| `GET/POST` | `/api/v1/services/` | Developer+ | CRUD services (`?environment=<id>`) |
| `GET/PUT/PATCH/DELETE` | `/api/v1/services/{id}/` | Developer+ | Détail + env_vars, domains, volumes, healthcheck |
| `POST` | `/api/v1/services/{id}/deploy/` | Operator+ | Déclencher un déploiement |
| `GET` | `/api/v1/services/{id}/deployments/` | Developer+ | 20 derniers déploiements |

### Deployments

| Méthode | URL | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/deployments/` | Operator+ | Lister les déploiements du workspace |
| `GET` | `/api/v1/deployments/{id}/` | Operator+ | Détail + events + rollback records |
| `POST` | `/api/v1/deployments/{id}/rollback/` | Operator+ | Rejouer ce déploiement |

### Catalog

| Méthode | URL | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/catalog/templates/` | Authentifié | Catalogue de templates |
| `GET` | `/api/v1/catalog/templates/{slug}/` | Authentifié | Détail template |
| `POST` | `/api/v1/catalog/templates/` | Operator+ | Publier un template |
| `POST` | `/api/v1/catalog/templates/{slug}/endorse/` | Operator+ | Certifier un template |

### RBAC — Hiérarchie des rôles workspace

```
admin (6) > maintainer (5) > operator (4) > developer (3) > viewer (2) > auditor (1)
```

Les niveaux sont cumulatifs : un `operator` peut tout faire depuis `developer` et `viewer`.

---

## Variables d'environnement — référence complète

| Variable | Défaut | Description |
|---|---|---|
| `SECRET_KEY` | — | Clé Django (obligatoire) |
| `DEBUG` | `False` | Mode debug |
| `ALLOWED_HOSTS` | `[]` | Hosts autorisés (liste séparée par virgules) |
| `DATABASE_URL` | — | URL PostgreSQL complète |
| `REDIS_BROKER_URL` | `redis://localhost:6379/0` | Broker Celery |
| `REDIS_CHANNELS_URL` | `redis://localhost:6379/1` | Layer Channels WebSocket |
| `FIELD_ENCRYPTION_KEY` | — | Clé Fernet AES-256 pour les secrets workspace |
| `CORS_ALLOWED_ORIGINS` | `[]` | Origins autorisés (prod) |

---

## DJANGO_SETTINGS_MODULE

| Contexte | Module |
|---|---|
| Développement local | `config.settings.development` |
| Production | `config.settings.production` |
| Tests (pytest) | `config.settings.development` (via `pyproject.toml`) |

Pour overrider : `export DJANGO_SETTINGS_MODULE=config.settings.development`

---

## Roadmap V1 — Semaine 1-2

- [x] Modèles de données complets (toute la hiérarchie Org→Deployment)
- [x] Migrations initiales
- [x] Factories factory-boy
- [x] Tests de base (modèles + middleware)
- [x] DRF serializers + viewsets (guide `05-api-drf.md`)
- [x] Middleware RBAC permissions

Voir [CHANGELOG.md](./CHANGELOG.md) pour le détail de chaque livraison.
