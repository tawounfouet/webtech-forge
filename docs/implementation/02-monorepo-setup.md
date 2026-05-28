# 02 — Monorepo Setup

> **ADR de référence :** ADR-002, ADR-003, ADR-014
> **Dépendances :** 01-architecture-overview.md

---

## Structure du monorepo

```
webtech-forge/
├── backend/                        # Control plane Django
│   ├── apps/
│   │   ├── accounts/               # Custom user model, auth, MFA
│   │   ├── organizations/          # Organization model
│   │   ├── workspaces/             # Workspace, membres, quotas, secrets
│   │   ├── projects/               # Project, ProjectRepository
│   │   ├── environments/           # Environment, PromotionPolicy
│   │   ├── services/               # Service, ServiceBinding, Domain
│   │   ├── deployments/            # Deployment, DeploymentEvent, Rollback
│   │   ├── activator/              # ActivatorRule, ActivatorExecution
│   │   ├── monitor/                # Monitor Hub API (lecture seule)
│   │   ├── catalog/                # ServiceTemplate, Endorsement
│   │   └── audit/                  # AuditLog, AuditMiddleware
│   ├── adapters/
│   │   ├── docker_adapter.py
│   │   ├── registry_adapter.py
│   │   ├── git_adapter.py
│   │   ├── traefik_adapter.py
│   │   ├── storage_adapter.py
│   │   └── metrics_adapter.py
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── celery.py
│   ├── manage.py
│   ├── requirements/
│   │   ├── base.txt
│   │   ├── dev.txt
│   │   └── prod.txt
│   └── Dockerfile
│
├── frontend/                       # Console Next.js
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── mfa/
│   │   └── (dashboard)/
│   │       ├── layout.tsx
│   │       ├── workspaces/
│   │       ├── projects/
│   │       ├── environments/
│   │       ├── services/
│   │       ├── deployments/
│   │       ├── monitor/            # Monitor Hub
│   │       ├── catalog/            # Templates
│   │       └── activator/          # Activator rules
│   ├── components/
│   │   ├── ui/                     # Composants génériques
│   │   ├── deployments/
│   │   ├── monitor/
│   │   └── activator/
│   ├── lib/
│   │   ├── api-client.ts           # Client DRF typé (généré depuis OpenAPI)
│   │   ├── ws-client.ts            # Client WebSocket avec auth
│   │   └── hooks/
│   ├── package.json
│   └── Dockerfile
│
├── infra/
│   ├── docker-compose.platform.yml # Déploiement de la plateforme
│   ├── docker-compose.dev.yml      # Override pour le développement local
│   ├── traefik/
│   │   ├── traefik.yml
│   │   └── dynamic/
│   ├── ansible/
│   │   ├── bootstrap-vps.yml
│   │   ├── deploy-platform.yml
│   │   └── roles/
│   └── terraform/
│       ├── dns.tf
│       ├── s3.tf
│       └── variables.tf
│
├── spec/                           # Diagrammes Mermaid exportables
│   ├── erd.mmd
│   ├── architecture-overview.mmd
│   └── deployment-workflow.mmd
│
├── docs/
│   ├── adr/                        # Architecture Decision Records
│   ├── implementation/             # Ce dossier
│   └── runbooks/
│
├── forge.yaml.schema.json          # JSON Schema du manifeste projet
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── build.yml
│       └── deploy.yml
└── Makefile                        # Commandes de dev courantes
```

---

## Outillage

### Python (backend)

```
# requirements/base.txt
Django==5.2.*
djangorestframework==3.15.*
django-filter==24.*
djangorestframework-simplejwt==5.*
django-otp==1.*           # MFA TOTP
django-encrypted-fields==1.*
channels==4.*
channels-redis==4.*
celery==5.*
redis==5.*
docker==7.*               # Docker SDK for Python
boto3==1.*                # S3-compatible
psycopg[binary]==3.*
daphne==4.*               # ASGI server
django-stubs[compatible-mypy]
```

```
# requirements/dev.txt
pytest==8.*
pytest-django==4.*
pytest-asyncio==0.23.*
factory-boy==3.*
faker==24.*
coverage==7.*
ruff==0.4.*               # linter + formatter
mypy==1.*
testcontainers==3.*       # Docker-in-Docker pour tests d'intégration
```

### Node.js (frontend)

```json
{
  "dependencies": {
    "next": "15.*",
    "react": "19.*",
    "react-dom": "19.*",
    "swr": "2.*",
    "zod": "3.*",
    "recharts": "2.*"
  },
  "devDependencies": {
    "typescript": "5.*",
    "openapi-typescript": "7.*",
    "playwright": "1.*",
    "@playwright/test": "1.*",
    "eslint": "9.*"
  }
}
```

---

## Makefile — commandes de dev courantes

```makefile
.PHONY: dev test lint migrate shell

dev:
	docker compose -f infra/docker-compose.dev.yml up

test:
	cd backend && pytest --cov=apps --cov-report=term-missing

lint:
	cd backend && ruff check . && mypy apps/
	cd frontend && npm run lint

migrate:
	cd backend && python manage.py migrate

shell:
	cd backend && python manage.py shell_plus

worker:
	cd backend && celery -A config.celery worker -l info -Q default,deployments

activator:
	cd backend && celery -A config.celery worker -l info -Q activator

beat:
	cd backend && celery -A config.celery beat -l info

generate-types:
	cd backend && python manage.py spectacular --file openapi.yaml
	cd frontend && npx openapi-typescript ../backend/openapi.yaml -o lib/api.d.ts
```

---

## Conventions de code

### Backend

- **Apps Django** : une app par domaine métier. Pas de logique business dans les vues — les vues délèguent aux services métier (`services.py`) ou aux adapters.
- **Naming** : `snake_case` pour tout sauf les classes. Les modèles Django sont au singulier (`Workspace`, pas `Workspaces`).
- **Imports** : absolus uniquement (`from apps.workspaces.models import Workspace`).
- **Ruff** comme linter et formatter (remplace Black + isort + Flake8).
- **Mypy** en mode strict sur les apps critiques (`deployments`, `activator`).

### Frontend

- **App Router** uniquement — pas de Pages Router.
- **Server Components** par défaut ; `use client` uniquement pour les composants interactifs (forms, WS).
- **Types générés** depuis OpenAPI — ne pas écrire les types à la main.
- **Zod** pour la validation côté client des formulaires.

---

## Variables d'environnement

```bash
# backend/.env (non commité — modèle dans .env.example)
SECRET_KEY=<django-secret-key>
DATABASE_URL=postgres://forge:password@localhost:5432/forge
REDIS_BROKER_URL=redis://localhost:6379/0
REDIS_CHANNELS_URL=redis://localhost:6380/0
REGISTRY_URL=localhost:5000
REGISTRY_SECRET=<registry-http-secret>
S3_BUCKET=webtech-forge-backups
S3_ENDPOINT_URL=https://s3.eu-west-3.amazonaws.com
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
ALLOWED_HOSTS=forge.internal,localhost
DEBUG=false
```
