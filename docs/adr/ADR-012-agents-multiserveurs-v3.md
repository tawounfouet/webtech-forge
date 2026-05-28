# ADR-012 — Mode multi-serveur par agents légers plutôt que Kubernetes

- **Statut :** Accepté
- **Priorité :** P2
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

En V3, WebTech Forge doit supporter plusieurs hôtes Docker pour distribuer les workloads (isolation client, capacité, géographie). Deux approches sont possibles :
1. Adopter Kubernetes comme orchestrateur multi-hôtes.
2. Implémenter un protocole d'agents légers entre le control plane et les nœuds Docker.

## Décision

Implémenter un **mode multi-serveur par agents légers** en V3, sans adopter Kubernetes.

### Architecture agents

```
Django Control Plane
    ↓  (HTTP + mTLS ou WebSocket sécurisé)
ForgeAgent (Python) sur chaque nœud
    ↓
Docker Engine local
```

Chaque `ForgeAgent` :
- S'enregistre auprès du control plane avec son inventaire (CPU, mémoire, Docker version, tags).
- Envoie des heartbeats toutes les 30 secondes.
- Reçoit des instructions de déploiement du control plane et les exécute localement.
- Rapporte l'état observé (containers running, healthchecks, métriques).

La reconciliation `état désiré vs état observé` se fait dans le control plane Django — pas dans l'agent.

```python
class ServerTarget(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    hostname = models.CharField(max_length=255, unique=True)
    agent_version = models.CharField(max_length=32)
    status = models.CharField(choices=[("online","Online"),("offline","Offline"),("degraded","Degraded")])
    last_heartbeat = models.DateTimeField()
    cpu_cores = models.PositiveIntegerField()
    memory_gb = models.FloatField()
    tags = models.JSONField(default=list)  # ["gpu", "high-mem", "eu-west"]
```

## Justification

- **Montée en complexité progressive :** des agents simples sont plus faciles à opérer qu'un cluster Kubernetes complet pour un PaaS interne.
- **Cohérence architecturale :** le même modèle `desired state + reconciliation` que Kubernetes, sans la complexité distribuée de son control plane.
- **La littérature Borg/Omega/Kubernetes** montre que la puissance des contrôleurs vient de la reconciliation explicite — extractible du framework K8s.
- **Kubernetes self-hosted V3 est une option de dernier recours** — si la densité ou la criticité le justifie, le `DockerAdapter` peut être remplacé par un `KubernetesAdapter` sans changer le control plane.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Kubernetes self-hosted dès V3 | Complexité opérationnelle majeure, etcd, CNI, CSI, HA du control plane K8s |
| Kubernetes managé (EKS, GKE) | Dépendance cloud, coût, lock-in |
| Docker Swarm | Déprécié, futur incertain |

## Conséquences

- `ForgeAgent` est un binaire Python packagé (ou image Docker) déployé sur chaque nœud via Ansible.
- La communication control plane ↔ agents est sécurisée par mTLS avec certificats gérés par le control plane.
- Le `ServerTarget` expose son inventaire dans le Monitor Hub pour la vue capacité cross-workspace.
- Le scheduling des déploiements sur les nœuds est déterministe (affinité par tags, bin-packing) — documenté dans la spec V3.
