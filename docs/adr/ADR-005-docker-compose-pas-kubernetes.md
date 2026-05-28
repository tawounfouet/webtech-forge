# ADR-005 — Docker Engine + Compose en V1/V2, Kubernetes différé

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

WebTech Forge doit choisir un runtime pour exécuter les workloads déployés par les utilisateurs. Les deux candidats naturels sont Docker Compose et Kubernetes.

La contrainte V1 est un **mono-serveur VPS**. La V3 cible un mode multi-serveurs avec agents.

## Décision

Utiliser **Docker Engine + Compose Spec** comme runtime des workloads en V1 et V2. **Kubernetes n'est pas adopté** tant que la densité de workloads, la criticité ou les contraintes d'isolation ne le justifient pas explicitement (V3+).

Le `DockerAdapter` abstrait les appels au Docker Engine API de façon à ce que l'ajout d'un runtime alternatif n'impacte pas le control plane.

## Justification

**Docker Compose est parfaitement adapté au contexte V1 :**
- Conçu explicitement pour les applications multi-conteneurs sur un seul hôte.
- YAML simple, peu de surface d'administration.
- Supporte services, réseaux nommés, volumes, healthchecks et secrets de façon native.
- La découverte Traefik via labels Docker est native et élimine toute configuration manuelle de routing.

**Kubernetes introduit un coût prématuré :**
- Un cluster Kubernetes de production exige un control plane distribué (etcd, kube-apiserver, kube-scheduler), un CNI, un CSI et une stratégie de HA.
- La littérature Borg/Omega/Kubernetes souligne que la puissance de K8s vient de la reconciliation distribuée — précisément ce qui est excessif pour un mono-VPS.
- Le rapport complexité/valeur est négatif en V1.

**La trajectoire vers le multi-serveur (V3) adopte un modèle d'agents légers**, pas Kubernetes, pour rester cohérent avec la philosophie de simplicité progressive.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Kubernetes dès V1 | Surcoût opérationnel majeur, HA et networking complexes, courbe d'apprentissage élevée |
| Nomad (HashiCorp) | Moins de ressources communautaires, intégration Traefik moins native |
| Docker Swarm | Déprécié dans les nouvelles versions de Docker, futur incertain |
| Podman + quadlets | Moins mature pour les déploiements programmatiques via SDK |

## Conséquences

- Le `DockerAdapter` utilise `docker-py` (Docker SDK for Python) pour toutes les opérations sur l'Engine API.
- Les services sont décrits par des specs Compose générées dynamiquement par le deployment engine.
- L'upgrade vers un runtime alternatif (K8s en V3) implique uniquement de remplacer le `DockerAdapter` — le control plane Django et l'ontologie sont inchangés.
- Les réseaux Docker nommés `forge-ws-{slug}` sont créés/supprimés par le `DockerAdapter` en même temps que le workspace.
