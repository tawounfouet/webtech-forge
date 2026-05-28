# ADR-006 — Traefik comme edge router principal

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

WebTech Forge doit exposer les services déployés par les utilisateurs sur des domaines publics ou internes, avec TLS automatique. Le routing doit être **dynamique** — chaque nouveau déploiement doit être routé sans redémarrer ou recharger manuellement le reverse proxy.

## Décision

Utiliser **Traefik** comme edge router principal, configuré avec le **provider Docker** pour la découverte automatique des services via labels.

```yaml
# Labels générés par le TraefikAdapter pour chaque service déployé
traefik.enable: "true"
traefik.http.routers.{service_id}.rule: "Host(`{domain}`)"
traefik.http.routers.{service_id}.tls: "true"
traefik.http.routers.{service_id}.tls.certresolver: "letsencrypt"
traefik.http.services.{service_id}.loadbalancer.server.port: "{internal_port}"
```

Pour les preview environments, Traefik supporte les **wildcard certificates** (DNS-01 challenge) permettant de router `pr-123.project.forge.internal` sans reconfiguration.

## Justification

- **Découverte dynamique native :** Traefik lit les labels Docker en temps réel. Un nouveau conteneur est routé en secondes sans action manuelle — essentiel pour un PaaS qui crée et détruit des services à la demande.
- **TLS automatique :** intégration Let's Encrypt ACME intégrée (HTTP-01 pour les domaines publics, DNS-01 pour les wildcards de preview environments).
- **Blue/green natif :** Traefik peut router vers un nouveau conteneur et couper l'accès à l'ancien via label uniquement.
- **Dashboard opérateur :** interface web intégrée pour visualiser les routes actives.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Nginx | Configuration statique à maintenir, reload nécessaire à chaque nouveau service, wildcard certs plus complexes |
| Caddy | Moins de ressources pour le provider Docker, moins mature pour les use cases PaaS |
| HAProxy | Pas de provider Docker natif, configuration très verbale |

## Conséquences

- Traefik est déployé dans le réseau `forge-edge` et a accès au socket Docker (`/var/run/docker.sock` en lecture seule).
- Le `TraefikAdapter` génère les labels pour chaque `Deployment` en phase Gold.
- La stratégie blue/green en phase Gold passe par la suppression du label `traefik.enable: "true"` sur l'ancien conteneur avant son arrêt.
- Les certificats Let's Encrypt sont stockés dans un volume persistant `traefik-certs`.
- Pour les preview environments (V2) : le challenge DNS-01 est configuré avec le provider du registrar (Cloudflare, OVH, etc.) — cette dépendance doit être documentée avant V2.
