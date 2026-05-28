# 13 — Infrastructure Docker Compose

> **ADR de référence :** ADR-004, ADR-005, ADR-007, ADR-009, ADR-016
> **Dépendances :** 01-architecture-overview.md, 15-isolation-reseau-docker.md

---

## docker-compose.platform.yml

Fichier complet de déploiement de la plateforme WebTech Forge elle-même.

```yaml
# infra/docker-compose.platform.yml
name: webtech-forge

x-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
    tag: "{{.Name}}"

x-restart: &always-restart
  restart: unless-stopped

services:

  # ── Reverse Proxy ────────────────────────────────────────────
  traefik:
    image: traefik:v3.0
    <<: *always-restart
    command:
      - "--api.insecure=false"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--providers.docker.network=forge-edge"
      - "--providers.file.directory=/traefik/dynamic"
      - "--providers.file.watch=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.web.http.redirections.entrypoint.to=websecure"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.email=${ACME_EMAIL}"
      - "--certificatesresolvers.letsencrypt.acme.storage=/certs/acme.json"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--metrics.prometheus=true"
      - "--metrics.prometheus.addEntryPointsLabels=true"
      - "--log.level=INFO"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik-certs:/certs
      - ./traefik/dynamic:/traefik/dynamic:ro
    networks:
      - forge-edge
      - forge-platform
    logging: *default-logging

  # ── Base de données ──────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    <<: *always-restart
    environment:
      POSTGRES_DB: forge
      POSTGRES_USER: forge
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pg-data:/var/lib/postgresql/data
    networks:
      - forge-platform
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U forge"]
      interval: 10s
      timeout: 5s
      retries: 5
    logging: *default-logging

  # ── Redis Broker (Celery) ────────────────────────────────────
  redis-broker:
    image: redis:7-alpine
    <<: *always-restart
    command: >
      redis-server
      --appendonly yes
      --maxmemory 512mb
      --maxmemory-policy noeviction
    volumes:
      - redis-broker-data:/data
    networks:
      - forge-platform
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
    logging: *default-logging

  # ── Redis Channel Layer (WebSocket) ─────────────────────────
  redis-channels:
    image: redis:7-alpine
    <<: *always-restart
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    networks:
      - forge-platform
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
    logging: *default-logging

  # ── Registry d'images ────────────────────────────────────────
  registry:
    image: registry:2
    <<: *always-restart
    ports:
      - "127.0.0.1:5000:5000"
    environment:
      REGISTRY_STORAGE_DELETE_ENABLED: "true"
      REGISTRY_HTTP_SECRET: ${REGISTRY_SECRET}
    volumes:
      - registry-data:/var/lib/registry
    networks:
      - forge-platform
    logging: *default-logging

  # ── Control Plane Django (ASGI) ──────────────────────────────
  api:
    build:
      context: ../backend
      dockerfile: Dockerfile
      target: production
    <<: *always-restart
    env_file: ../.env
    depends_on:
      postgres:
        condition: service_healthy
      redis-broker:
        condition: service_healthy
    command: daphne -b 0.0.0.0 -p 8000 config.asgi:application
    volumes:
      - static-files:/app/staticfiles
    networks:
      - forge-platform
    labels:
      traefik.enable: "true"
      traefik.http.routers.api.rule: "Host(`${FORGE_DOMAIN}`) && PathPrefix(`/api`)"
      traefik.http.routers.api.tls: "true"
      traefik.http.routers.api.tls.certresolver: "letsencrypt"
      traefik.http.services.api.loadbalancer.server.port: "8000"
      traefik.http.routers.ws.rule: "Host(`${FORGE_DOMAIN}`) && PathPrefix(`/ws`)"
      traefik.http.routers.ws.tls: "true"
    logging: *default-logging

  # ── Console Next.js ──────────────────────────────────────────
  console:
    build:
      context: ../frontend
      dockerfile: Dockerfile
      target: production
    <<: *always-restart
    env_file: ../frontend/.env.local
    depends_on:
      - api
    networks:
      - forge-platform
    labels:
      traefik.enable: "true"
      traefik.http.routers.console.rule: "Host(`${FORGE_DOMAIN}`)"
      traefik.http.routers.console.tls: "true"
      traefik.http.routers.console.tls.certresolver: "letsencrypt"
      traefik.http.services.console.loadbalancer.server.port: "3000"
    logging: *default-logging

  # ── Celery Worker (deployments, backups) ──────────────────────
  celery-worker:
    build:
      context: ../backend
      dockerfile: Dockerfile
      target: production
    <<: *always-restart
    env_file: ../.env
    depends_on:
      - postgres
      - redis-broker
    command: >
      celery -A config.celery worker
      -l info
      -Q default,deployments,backups
      --concurrency 4
      --hostname forge-worker@%h
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    networks:
      - forge-platform
    logging: *default-logging

  # ── Celery Activator Worker ───────────────────────────────────
  celery-activator:
    build:
      context: ../backend
      dockerfile: Dockerfile
      target: production
    <<: *always-restart
    env_file: ../.env
    depends_on:
      - redis-broker
    command: >
      celery -A config.celery worker
      -l info
      -Q activator
      --concurrency 2
      --hostname forge-activator@%h
    networks:
      - forge-platform
    logging: *default-logging

  # ── Celery Beat ───────────────────────────────────────────────
  celery-beat:
    build:
      context: ../backend
      dockerfile: Dockerfile
      target: production
    <<: *always-restart
    env_file: ../.env
    depends_on:
      - redis-broker
      - postgres
    command: >
      celery -A config.celery beat
      -l info
      --scheduler django_celery_beat.schedulers:DatabaseScheduler
    networks:
      - forge-platform
    logging: *default-logging

  # ── Observabilité ────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:v2.51.0
    <<: *always-restart
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=30d"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    networks:
      - forge-platform
    logging: *default-logging

  grafana:
    image: grafana/grafana:10.4.0
    <<: *always-restart
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
      GF_SERVER_DOMAIN: ${FORGE_DOMAIN}
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./grafana/datasources:/etc/grafana/provisioning/datasources:ro
    networks:
      - forge-platform
    labels:
      traefik.enable: "true"
      traefik.http.routers.grafana.rule: "Host(`grafana.${FORGE_DOMAIN}`)"
      traefik.http.routers.grafana.tls: "true"
    logging: *default-logging

  loki:
    image: grafana/loki:2.9.0
    <<: *always-restart
    command: -config.file=/etc/loki/config.yml
    volumes:
      - ./loki/config.yml:/etc/loki/config.yml:ro
      - loki-data:/loki
    networks:
      - forge-platform
    logging: *default-logging

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.49.1
    <<: *always-restart
    privileged: true
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker:/var/lib/docker:ro
    networks:
      - forge-platform
    logging: *default-logging

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:v0.15.0
    <<: *always-restart
    environment:
      DATA_SOURCE_NAME: "postgresql://forge:${POSTGRES_PASSWORD}@postgres:5432/forge?sslmode=disable"
    networks:
      - forge-platform
    logging: *default-logging

networks:
  forge-platform:
    driver: bridge
    internal: true
    name: forge-platform
  forge-edge:
    driver: bridge
    name: forge-edge

volumes:
  pg-data:
  redis-broker-data:
  registry-data:
  traefik-certs:
  static-files:
  prometheus-data:
  grafana-data:
  loki-data:
```

---

## docker-compose.dev.yml (override local)

```yaml
# infra/docker-compose.dev.yml
services:
  api:
    command: daphne -b 0.0.0.0 -p 8000 config.asgi:application
    volumes:
      - ../backend:/app
    environment:
      DEBUG: "true"

  console:
    command: npm run dev
    volumes:
      - ../frontend:/app
      - /app/node_modules
    environment:
      NODE_ENV: development

  celery-worker:
    command: celery -A config.celery worker -l debug -Q default,deployments --concurrency 2
    volumes:
      - ../backend:/app
```

Lancer en développement :
```bash
docker compose -f infra/docker-compose.platform.yml -f infra/docker-compose.dev.yml up
```
