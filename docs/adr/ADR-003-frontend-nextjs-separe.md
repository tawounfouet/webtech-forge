# ADR-003 — Frontend Next.js séparé du backend

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Deux approches pour l'interface opérateur :
1. **Frontend intégré au backend Django** (Django templates + HTMX),
2. **Frontend Next.js découplé** communiquant avec l'API DRF.

## Décision

Conserver un **frontend Next.js App Router** déployé dans son propre conteneur Docker, communiquant exclusivement avec l'API DRF et le serveur WebSocket Channels.

```
frontend/
├── app/
│   ├── (auth)/
│   ├── (dashboard)/
│   │   ├── workspaces/
│   │   ├── projects/
│   │   ├── services/
│   │   ├── deployments/
│   │   ├── monitor/        ← Monitor Hub
│   │   ├── catalog/        ← Service Templates
│   │   └── activator/      ← Forge Activator rules
│   └── layout.tsx
├── components/
└── lib/
    └── api-client.ts       ← client DRF typé
```

## Justification

- **Séparation claire UI/API :** l'API DRF reste la source de vérité, consommable par d'autres clients (CLI, webhooks, intégrations).
- **Self-hosting :** Next.js se déploie en mode standalone Docker sans dépendance à Vercel.
- **App Router :** mature pour les tableaux de bord internes, supporte le streaming SSR, les Server Actions et les layouts imbriqués.
- **Temps réel natif :** intégration WebSocket simple avec les Consumer Channels Django.
- **Séparation des cycles de release :** frontend et backend peuvent être mis à jour indépendamment.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Django templates + HTMX | Bon pour des formulaires simples, insuffisant pour dashboards temps réel, graphiques métriques et logs streamés |
| Vue.js / Nuxt | Écosystème plus petit pour les dashboards d'ops ; moins de composants de visualisation matures |
| React SPA sans framework | Pas de SSR, routing manuel, pas d'optimisation d'assets intégrée |

## Conséquences

- Le frontend est un service `web` dans le `docker-compose.platform.yml` avec son propre build multi-stage.
- L'API DRF expose CORS configuré pour l'URL de la console uniquement.
- Les types des réponses API sont générés depuis le schéma OpenAPI (`openapi-typescript`) pour maintenir la cohérence.
- Le Monitor Hub, le Forge Activator UI et le catalogue de templates sont des sections de la même app Next.js.
