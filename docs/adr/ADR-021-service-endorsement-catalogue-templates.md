# ADR-021 — Service Endorsement & Catalogue de Templates

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Sans gouvernance des templates de services, chaque équipe reconfigure de zéro ses services Django, Next.js, PostgreSQL — avec des variantes non standardisées, des healthchecks oubliés, des politiques de backup différentes. Cela crée de la dette opérationnelle et des incohérences de sécurité.

Inspiré du système d'**endorsement de Microsoft Fabric** (Promoted / Certified / Preview pour les datasets et rapports), WebTech Forge peut offrir un catalogue de templates de services validés par l'équipe plateforme.

## Décision

Implémenter un **Service Endorsement & Catalogue de Templates** en V1 avec trois niveaux de validation.

### Niveaux d'endorsement

| Niveau | Signification | Qui peut endorser |
|---|---|---|
| `experimental` | Non validé, usage à risque propre | Tout `WorkspaceAdmin` |
| `promoted` | Recommandé par l'équipe plateforme | `OrganizationOwner` |
| `certified` | Validé en production, conforme aux standards | `OrganizationOwner` avec quorum de 2 approbateurs |

### Portée des templates

- **Template global (workspace=null) :** visible par toute l'Organisation. Créé par `OrganizationOwner`.
- **Template workspace :** visible uniquement dans le workspace. Créé par `WorkspaceAdmin`.

### Exemple de template certifié

```json
{
  "name": "Django Web + PostgreSQL",
  "endorsement": "certified",
  "template_config": {
    "service_type": "web",
    "runtime": "dockerfile",
    "internal_port": 8000,
    "healthcheck": {
      "path": "/health/",
      "interval": "30s",
      "timeout": "5s",
      "retries": 3
    },
    "env_defaults": {
      "DJANGO_SETTINGS_MODULE": "config.settings.production",
      "PYTHONUNBUFFERED": "1"
    },
    "required_secrets": ["DATABASE_URL", "SECRET_KEY"],
    "linked_services": [
      {
        "type": "database",
        "image": "postgres:16-alpine",
        "backup": {"enabled": true, "schedule": "0 2 * * *"}
      }
    ]
  }
}
```

### Endpoints

```
GET  /api/v1/catalog/templates                      → liste des templates visibles
GET  /api/v1/catalog/templates/{id}                 → détail
POST /api/v1/catalog/templates                      → créer un template (WorkspaceAdmin)
POST /api/v1/catalog/templates/{id}/endorse         → endorser (OrganizationOwner)
POST /api/v1/environments/{id}/services?template={id} → créer un service depuis template
```

## Justification

- **Fabric Endorsement :** valide le concept de certification progressive des assets — les équipes font confiance aux templates certifiés sans avoir à les auditer elles-mêmes.
- **Réduction du toil :** un développeur qui crée un service Django depuis un template certifié a immédiatement un healthcheck, une politique de backup, des secrets requis et des defaults de sécurité — sans configuration manuelle.
- **Gouvernance :** l'équipe plateforme contrôle quels templates sont recommandés (promoted) ou certifiés — réduit les variantes non conformes.
- **Traçabilité :** chaque service créé depuis un template a une référence au template d'origine — si le template est mis à jour, les services dérivés peuvent être notifiés.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Pas de templates, tout en UI | Chaque équipe reconfigure de zéro, pas de standardisation |
| Templates uniquement dans Git | Pas de gouvernance, pas de versioning au niveau plateforme, pas de visibilité centralisée |

## Conséquences

- Le catalogue de templates est visible dans la section `/catalog` de la console Next.js.
- Les templates certifiés sont mis en avant lors de la création d'un nouveau service.
- Un service créé depuis un template enregistre `Service.template_id` — utilisé pour les rapports Monitor Hub ("80 % des services Django utilisent le template certifié").
- La mise à jour d'un template certifié notifie les `WorkspaceAdmin` des workspaces qui l'utilisent (Activator rule de type `template_update`).
