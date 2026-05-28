# ADR-007 — PostgreSQL 16 local comme base du control plane en V1

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Le control plane Django nécessite une base de données relationnelle pour persister l'état désiré de la plateforme (workspaces, services, déploiements, audit logs, règles Activator, etc.). Le choix est entre une instance PostgreSQL auto-hébergée et un service PostgreSQL managé (cloud).

## Décision

Utiliser **PostgreSQL 16 auto-hébergé** sur le même VPS que le control plane en V1. La migration vers un PostgreSQL managé est prévue en V2/V3 si la criticité ou la charge opérationnelle le justifient.

## Justification

- **Coût V1 :** un PostgreSQL managé (RDS, Supabase, Neon) ajoute un coût mensuel fixe non justifié pour un usage interne à faible trafic initial.
- **Contrôle total :** accès direct aux fichiers WAL, possibilité de PITR maison, accès SSH pour debug.
- **Simplicité :** une seule infrastructure, un seul VPS à gérer.
- **PostgreSQL 16 :** version stable avec support jusqu'en 2028, performances solides pour les workloads OLTP du control plane.

**Conditions de cette décision :**
- Un processus de backup quotidien avec `pg_dump` et upload S3 est impératif dès V1.
- Un **restore drill mensuel** est obligatoire — un backup non testé n'est pas une stratégie de reprise.
- La rétention de données dans PostgreSQL est gérée explicitement (audit logs, deployment events : 90 jours par défaut).

## Alternatives considérées

| Alternative | Rejet en V1 |
|---|---|
| PostgreSQL managé (RDS, Supabase) | Coût supérieur, dépendance cloud, surcoût pour V1 interne |
| SQLite | Pas adapté à la concurrence (Celery workers multiples + API simultanée) |
| MySQL / MariaDB | Écosystème Django/migrations moins riche, JSON support inférieur à PostgreSQL |

## Conséquences

- PostgreSQL tourne dans le `docker-compose.platform.yml` avec un volume persistant `pg-data`.
- La sauvegarde suit la procédure décrite dans `runbooks/backup-restore.md`.
- `pg_dump` + upload S3 + vérification checksum = tâche Celery Beat quotidienne à 2h00.
- En V2, si le restore drill révèle des faiblesses ou si la charge augmente significativement, migration vers PostgreSQL managé avec PITR intégré.
- `DATABASES["default"]["CONN_MAX_AGE"] = 60` pour le pool de connexions Django.
