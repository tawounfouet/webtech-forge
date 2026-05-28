# CHANGELOG — WebTech Forge Backend

Suivi des livraisons du backend Django, par jalon du roadmap V1.
Format : [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

## [Unreleased]

### À faire — Semaine 3-4 (prochain jalon)

- [ ] Workers Celery — pipeline Medallion `run_deployment` (Bronze→Silver→Gold)
- [ ] WebSocket consumer `DeploymentLogConsumer` — streaming logs en temps réel
- [ ] Tests DRF — `APIClient` + factories pour tous les viewsets
- [ ] Adapters Docker/Git/Traefik — implémentation réelle (guide `07-deployment-engine.md`)
- [ ] `GET /api/v1/audit/` — endpoint AuditLog
- [ ] `GET /api/v1/monitor/` — endpoint Monitor Hub métriques
- [ ] Intégration GitHub Webhook — `apps/integrations/views.py`

---

## [0.2.0] — 2026-05-28 — API REST + RBAC

### Ajouté

**Permissions RBAC** (`apps/workspaces/permissions.py`)

- `WorkspacePermission` — classe de base ; évalue `request.workspace_role` injecté par `WorkspaceMiddleware` contre une hiérarchie numérique (`admin=6` → `auditor=1`)
- Concrètes : `IsWorkspaceAdmin`, `IsMaintainerOrAbove`, `IsOperatorOrAbove`, `IsDeveloperOrAbove`, `IsViewerOrAbove`
- `has_object_permission` délègue à `has_permission` — l'isolation objet est garantie au niveau `get_queryset()` (filtre `workspace`)

**Serializers** (7 apps)

| App | Serializers |
|---|---|
| `organizations` | `OrganizationSerializer` |
| `workspaces` | `WorkspaceSerializer`, `WorkspaceMemberSerializer`, `WorkspaceSecretSerializer` (value write-only), `WorkspaceQuotaSerializer` |
| `projects` | `ProjectSerializer`, `ProjectDetailSerializer`, `ProjectRepositorySerializer` |
| `environments` | `EnvironmentSerializer`, `EnvironmentDetailSerializer`, `PromotionPolicySerializer` |
| `services` | `ServiceSerializer`, `ServiceDetailSerializer`, `ServiceCreateSerializer`, `ServiceEnvVarSerializer`, `DomainSerializer`, `VolumeSerializer`, `HealthcheckSerializer`, `ServiceBindingSerializer` |
| `deployments` | `DeploymentListSerializer`, `DeploymentDetailSerializer`, `DeploymentEventSerializer`, `RollbackRecordSerializer` |
| `catalog` | `ServiceTemplateSerializer`, `ServiceTemplateDetailSerializer` |

**ViewSets + URLs**

| App | Classe | Endpoints clés |
|---|---|---|
| `organizations` | `OrganizationViewSet` | `GET/POST /api/v1/organizations/` — filtré sur memberships user |
| `workspaces` | `WorkspaceViewSet` | CRUD + actions `members`, `member_delete`, `secrets`, `quota` |
| `projects` | `ProjectViewSet` | CRUD + action `repositories` |
| `environments` | `EnvironmentViewSet` | CRUD, filtre `?project=<id>`, détail inclut `PromotionPolicy` |
| `services` | `ServiceViewSet` | CRUD + `deploy` (POST, Operator+) + `deployments` (GET) |
| `deployments` | `DeploymentViewSet` | Liste + détail + `rollback` (POST, Operator+) — lecture seule |
| `catalog` | `ServiceTemplateViewSet` | CRUD + `endorse` (POST, Operator+) — monté sur `/api/v1/catalog/` |

**Autres**

- `config/urls.py` : constante `API = "api/v1/"` extraite (supprime la duplication S1192) ; catalog monté sur `/api/v1/catalog/` conformément au guide `05-api-drf.md`
- `apps/deployments/tasks.py` : stub `run_deployment` ajouté (queue `deployments`) — sera implémenté dans le jalon 0.3.0

### Règles d'architecture respectées

- Chaque `get_queryset()` filtre systématiquement par `request.workspace` — aucune fuite de données inter-workspace possible
- Les secrets (`WorkspaceSecret.value`) ne sont jamais exposés en lecture via l'API (champ `write_only=True`)
- Les mutations sur les membres et quotas sont réservées au rôle `admin` du workspace

---

## [0.1.0] — 2026-05-28 — Fondations Django + Modèles + Tests

### Ajouté

**Bootstrap du projet**

- `pyproject.toml` : backend `setuptools.build_meta`, dépendances avec planchers `>=` (pas de pins stricts), `[dev]` extras
- `config/settings/base.py` : INSTALLED_APPS, DRF + SimpleJWT (60min/7j), Django Channels, Celery Beat, structlog LOGGING (`foreign_pre_chain` + `remove_processors_meta`)
- `config/settings/development.py` / `production.py` : overrides par environnement
- `config/celery.py` : auto-discovery, Beat schedules (activator 60s, backup 02:00, cleanup dimanche 03:00)
- `config/asgi.py` : routing HTTP + WebSocket (Channels)

**Modèles de données — hiérarchie complète**

```
Organization → Workspace → Project → Environment → Service → Deployment
```

| App | Modèles |
|---|---|
| `accounts` | `User` (email login, MFA, `AbstractUser`) |
| `organizations` | `Organization` |
| `workspaces` | `Workspace`, `WorkspaceMember` (6 rôles RBAC), `WorkspaceSecret` (AES-256 via `encrypted_model_fields`), `WorkspaceQuota` |
| `projects` | `Project`, `ProjectRepository` (webhook_secret) |
| `environments` | `Environment` (4 kinds), `PromotionPolicy` |
| `services` | `Service` (7 types, 3 runtimes), `ServiceEnvVar`, `Domain`, `Volume`, `Healthcheck`, `ServiceBinding` |
| `deployments` | `Deployment` (10 statuts, pipeline Medallion Bronze/Silver/Gold), `DeploymentEvent`, `RollbackRecord` |
| `activator` | `ActivatorRule`, `ActivatorExecution` |
| `monitor` | `ServiceMetric`, `ServiceHealthCheck` |
| `catalog` | `ServiceTemplate` (3 niveaux : experimental/promoted/certified) |
| `audit` | `AuditLog` |

**Migrations**

- 68 migrations appliquées au total (vérifié : `python manage.py migrate`)
- Dépendance circulaire `Service ↔ Deployment` résolue en 3 étapes :
  - `services/0001_initial` : crée `Service` sans `active_deployment`
  - `deployments/0001_initial` : crée `Deployment` avec FK → `Service`
  - `services/0002_service_active_deployment` : ajoute `Service.active_deployment` → `Deployment`

**Infrastructure**

- `WorkspaceMiddleware` : résout le workspace depuis `X-Workspace-Slug` ou l'URL (`/api/v1/workspaces/<slug>/…`) ; injecte `request.workspace` et `request.workspace_role`
- `AuditMiddleware` : capture IP (`X-Forwarded-For` ou `REMOTE_ADDR`) et user-agent
- Adapters hexagonaux : `DockerAdapter`, `GitAdapter`, `TraefikAdapter`, `RegistryAdapter`, `StorageAdapter`, `MetricsAdapter`

**Tests**

- 20 factories factory-boy (`tests/factories.py`) couvrant toute la hiérarchie
- `tests/conftest.py` : fixtures pytest-django (`db`, `workspace`, `user`, `membership`)
- `test_models/` : hiérarchie complète, round-trip chiffrement `WorkspaceSecret`, transitions `Deployment`
- `test_middleware/` : résolution workspace depuis header et URL, 403 si non membre

### Corrigé (bootstrap — voir `docs/changelog/2026-05-28-backend-setup-fixes.md`)

- **FIX-001** `pyproject.toml` : `setuptools.backends.legacy:build` → `setuptools.build_meta`
- **FIX-002** `pyproject.toml` : ajout `[tool.setuptools.packages.find]` pour flat-layout multi-packages
- **FIX-003** `pyproject.toml` : `django-celery-beat==2.7.*` → `>=2.8` (compatibilité Django 5.2)
- **FIX-004** `models.py` + migration : `encrypted_fields` → `encrypted_model_fields` (nom du module Python)
- **FIX-005** `.env` : `FIELD_ENCRYPTION_KEY` — clé Fernet doit inclure le `=` final (padding base64)
- **FIX-006** `base.py` : `processor=` (string) → `processors=` (liste de callables instanciés)
- **FIX-007** `base.py` : `wrap_for_formatter` sorti de `ProcessorFormatter.processors` → remplacé par `remove_processors_meta` (le bon pattern structlog 24.x)

---

## [0.0.0] — 2026-05-28 — Initialisation du dépôt

### Ajouté

- `.gitignore` Python/Django/Node
- 22 ADRs (`docs/adr/ADR-001` à `ADR-022`)
- 23 guides d'implémentation (`docs/implementation/01` à `23`)
- `README.md` racine du projet
