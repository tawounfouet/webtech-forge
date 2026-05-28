# Changelog — 2026-05-28 — Corrections setup backend Django

> Corrections appliquées lors du premier `pip install` + `python manage.py migrate` du backend WebTech Forge.
> Environnement : macOS Darwin 25.4, Python 3.12.13, PostgreSQL local (pgAdmin, user `postgres`), sans Docker.

---

## [FIX-001] `pyproject.toml` — Build backend invalide

**Fichier :** `src/backend/pyproject.toml`

**Symptôme :**
```
BackendUnavailable: Cannot import 'setuptools.backends.legacy'
```

**Cause :** `setuptools.backends.legacy:build` est un chemin expérimental non exposé dans toutes les versions de setuptools. Ce n'est pas le backend standard.

**Correction :**
```toml
# Avant
build-backend = "setuptools.backends.legacy:build"

# Après
build-backend = "setuptools.build_meta"
```

`setuptools.build_meta` est le backend PEP 517 stable depuis setuptools 40+.

---

## [FIX-002] `pyproject.toml` — Découverte de packages multi-racine

**Fichier :** `src/backend/pyproject.toml`

**Symptôme :**
```
error: Multiple top-level packages discovered in a flat-layout: ['apps', 'config', 'adapters'].
```

**Cause :** setuptools en flat-layout refuse plusieurs packages racine sans configuration explicite.

**Correction :** Ajout d'une section de découverte explicite :
```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["apps*", "config*", "adapters*"]
```

---

## [FIX-003] `pyproject.toml` — Conflits de dépendances Django 5.2

**Fichier :** `src/backend/pyproject.toml`

**Symptôme :**
```
django-celery-beat 2.7.0 depends on Django<5.2 and >=2.2
ResolutionImpossible
```

**Cause :** `django-celery-beat==2.7.0` impose `Django<5.2`. On utilise Django 5.2 LTS.

**Corrections :**

| Package | Avant | Après | Raison |
|---|---|---|---|
| `django-celery-beat` | `==2.7.*` | `>=2.8` | 2.7.x cap Django<5.2 ; 2.8+ supporte Django 5.x |
| `django-celery-results` | `==2.5.*` | `>=2.5.1` | 2.5.0 avait la même contrainte |
| `psycopg[binary]` | `==3.2.*` | `>=3.2,<4` | Plus souple, même contrainte effective |
| `django-otp` | `==1.5.*` | `>=1.5` | Évite blocages sur dépendances transitives |
| `qrcode[pil]` | `==7.*` | `>=7,<8` | Idem |
| `django-encrypted-model-fields` | `==0.6.*` | `>=0.6` | Idem |
| `django-stubs` | `==5.*` | `>=5` | Idem |
| `mypy` | `==1.10.*` | `>=1.10,<2` | Idem |

**Règle générale :** Les dépendances runtime dans `pyproject.toml` doivent utiliser `>=x.y` (plancher) plutôt que `==x.y.*` (pin strict). Le pin strict est réservé au `requirements.lock` généré par `pip freeze`.

---

## [FIX-004] `apps/workspaces/models.py` + migration — Mauvais nom de module

**Fichiers :**
- `src/backend/apps/workspaces/models.py`
- `src/backend/apps/workspaces/migrations/0001_initial.py`

**Symptôme :**
```
ModuleNotFoundError: No module named 'encrypted_fields'
```

**Cause :** Le package PyPI `django-encrypted-model-fields` expose son module Python sous `encrypted_model_fields` (avec `model` dans le nom), pas `encrypted_fields`.

**Correction :**
```python
# Avant
from encrypted_fields.fields import EncryptedTextField

# Après
from encrypted_model_fields.fields import EncryptedTextField
```

Même correction dans la migration (import + usage sur le champ `value` de `WorkspaceSecret`).

---

## [FIX-005] `.env` — Clé Fernet mal formatée

**Fichier :** `src/backend/.env` (fichier local, non versionné)

**Symptôme :**
```
ImproperlyConfigured: FIELD_ENCRYPTION_KEY defined incorrectly:
Fernet key must be 32 url-safe base64-encoded bytes.
```

**Cause :** La variable `FIELD_ENCRYPTION_KEY` était présente dans `.env` sans valeur (ligne vide ou `FIELD_ENCRYPTION_KEY` sans `=valeur`). Une clé Fernet valide est une chaîne base64 url-safe de 44 caractères se terminant généralement par `=`.

**Solution :** Générer une clé valide :
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Exemple de sortie : kH9fN5Mnt20uDlRgC_3AZ_EvZzsppY5QofU4Yg7lqvw=
```

Puis dans `.env` :
```env
FIELD_ENCRYPTION_KEY=kH9fN5Mnt20uDlRgC_3AZ_EvZzsppY5QofU4Yg7lqvw=
```

**Note :** Le `=` final fait partie de la clé (padding base64) — ne pas le supprimer.

---

## [FIX-006] `config/settings/base.py` — Config structlog invalide

**Fichier :** `src/backend/config/settings/base.py`

**Symptôme :**
```
TypeError: 'str' object is not callable
```
Répété sur chaque log Django (accès `/admin/`, static files, etc.).

**Cause :** La config `LOGGING` utilisait :
```python
"processor": "structlog.processors.JSONRenderer",  # chaîne, pas un callable
```

L'API `structlog.stdlib.ProcessorFormatter` depuis structlog 21+ attend :
- La clé `processors` (pluriel, liste de callables instanciés), pas `processor` (singulier, chaîne)
- Des callables Python (instances), jamais des chemins en string

**Correction :**
```python
# Avant — invalide
"formatters": {
    "json": {
        "()": "structlog.stdlib.ProcessorFormatter",
        "processor": "structlog.processors.JSONRenderer",  # ← chaîne
    },
},

# Après — correct (mais incomplet — voir FIX-007)
_LOG_PRE_CHAIN = [
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
    structlog.stdlib.ExtraAdder(),
]

"formatters": {
    "console": {
        "()": "structlog.stdlib.ProcessorFormatter",
        "processors": [
            *_LOG_PRE_CHAIN,                                          # ← ENCORE FAUX (voir FIX-007)
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
    },
},
```

`structlog.configure()` est également appelé pour initialiser le logger structlog utilisable dans le code applicatif via `structlog.get_logger()`.

---

## [FIX-007] `config/settings/base.py` — Ordre des processors `ProcessorFormatter`

**Fichier :** `src/backend/config/settings/base.py`

**Symptôme :**
```
AttributeError: 'tuple' object has no attribute 'pop'
  File ".../structlog/dev.py", line 713, in __call__
    stack = event_dict.pop("stack", None)
```
Répété sur chaque log Django après FIX-006.

**Cause réelle** (après lecture du source structlog 24.x `stdlib.py:1115-1128`) :

`wrap_for_formatter` est un **renderer final pour `structlog.configure()`**, pas un processor intermédiaire de `ProcessorFormatter.processors`. Il retourne un tuple :
```python
return (event_dict,), {"extra": {"_logger": logger, "_name": name}}
```
Ce tuple est dépacké par Python `logging` lors de l'appel au logger stdlib (`logger.info(*args, **kwargs)`). Quand on place `wrap_for_formatter` dans `ProcessorFormatter.processors`, la boucle `format()` fait :
```python
ed = wrap_for_formatter(logger, meth_name, ed)  # ← ed devient un tuple !
ed = ConsoleRenderer()(logger, meth_name, ed)   # ← ConsoleRenderer reçoit un tuple → AttributeError
```

`wrap_for_formatter` n'appartient QUE dans `structlog.configure(processors=[..., wrap_for_formatter])`.

**Correction :**
Dans `ProcessorFormatter.processors`, utiliser `remove_processors_meta` (élimine les clés internes `_record` et `_from_structlog` ajoutées par `format()`) suivi du renderer :

```python
_LOG_PRE_CHAIN = [
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
    structlog.stdlib.ExtraAdder(),
]

"formatters": {
    "console": {
        "()": "structlog.stdlib.ProcessorFormatter",
        "foreign_pre_chain": _LOG_PRE_CHAIN,          # ← enrichit les records Django/stdlib
        "processors": [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,  # ← strip _record/_from_structlog
            structlog.dev.ConsoleRenderer(colors=False),
        ],
    },
    "json": {
        "()": "structlog.stdlib.ProcessorFormatter",
        "foreign_pre_chain": _LOG_PRE_CHAIN,
        "processors": [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    },
},
```

**Règle :** `wrap_for_formatter` → uniquement dans `structlog.configure()` (dernière position). `ProcessorFormatter.processors` → `remove_processors_meta` + renderer uniquement.

---

## [CONTEXT] Setup local sans Docker

PostgreSQL créé via pgAdmin (installation native macOS) :
- User : `postgres` (défaut)
- Password : renseigné lors de l'installation
- Base de données : à créer manuellement dans pgAdmin avant `migrate`

`DATABASE_URL` correspondant dans `.env` :
```env
DATABASE_URL=postgres://postgres:VOTRE_PASSWORD@localhost:5432/webtech_forge
```

Redis : non démarré à cette étape (non requis pour `migrate` + `runserver` sans Celery).

---

## Résultat final

```
python manage.py migrate    → 68 migrations appliquées ✓
python manage.py runserver  → Django 5.2.14 démarré sur http://127.0.0.1:8000/ ✓
/admin/                     → Page de login Django Admin accessible ✓
```

Logs propres après FIX-007 — plus de `TypeError` ni `AttributeError` structlog.
