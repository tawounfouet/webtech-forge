# ADR-002 — Control plane en Django 5.x Modular Monolith + DRF

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Le control plane de WebTech Forge est un système d'état, de règles, d'autorisations, d'événements et d'orchestration. Il fallait choisir entre :
- une architecture microservices (plusieurs processus/services indépendants),
- un monolithe modulaire (un seul processus décomposé en modules internes clairs).

La V1 cible un mono-serveur VPS avec une équipe restreinte. Le budget opérationnel et cognitif est limité.

## Décision

Construire le control plane comme un **Django 5.2 LTS modulith** avec **Django REST Framework** pour l'API.

Structure interne par domaine (apps Django) :

```
backend/
├── apps/
│   ├── organizations/
│   ├── workspaces/
│   ├── projects/
│   ├── environments/
│   ├── services/
│   ├── deployments/
│   ├── activator/
│   ├── monitor/
│   ├── catalog/
│   └── audit/
├── adapters/
│   ├── docker_adapter.py
│   ├── git_adapter.py
│   ├── traefik_adapter.py
│   ├── registry_adapter.py
│   ├── storage_adapter.py
│   └── metrics_adapter.py
└── config/
```

Les apps Django communiquent via imports Python directs et signaux Django — pas via HTTP ou message broker.

## Justification

- **Simplicité opérationnelle :** un seul processus à déployer, déboguer et monitorer en V1.
- **Coût cognitif réduit :** une seule base de code, une seule migration, un seul déploiement.
- **Google SRE :** insiste sur la valeur de la simplicité opérationnelle pour la stabilité.
- **Azure :** rappelle que les microservices introduisent des coûts de communication, des frontières de responsabilité et des défis de résilience supplémentaires.
- **NIST SP 800-204 :** montre qu'une architecture microservices impose des problématiques de sécurité plus nombreuses (gateway, service discovery, sécurisation inter-services).

Django 5.2 est la version LTS actuelle — support garanti jusqu'en avril 2028.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Microservices dès V1 | Surcoût opérationnel majeur sans bénéfice à cette échelle |
| FastAPI | Écosystème admin, ORM, permissions et migrations moins mature que Django pour un control plane |
| Go / Rust | Courbe d'apprentissage élevée, pas d'écosystème équivalent à Django Admin pour l'opérationnel |

## Conséquences

- La frontière entre modules est imposée par la structure des apps Django, pas par des processus séparés.
- Le passage à des microservices (si jamais justifié) se fait en extrayant des apps en services autonomes — la structure modulaire rend cette migration moins douloureuse.
- `django-stubs` et `mypy` sont utilisés pour maintenir la rigueur de typage malgré la nature dynamique de Python.
- Un custom user model Django est défini dès la première migration (impossible à changer après).
