# 19 — Gestion des secrets

> **ADR de référence :** ADR-010
> **Dépendances :** 04-modeles-donnees.md, 18-securite.md

---

## V1 — Chiffrage applicatif

Les secrets workloads sont chiffrés au repos dans PostgreSQL avec `django-encrypted-fields` (AES-256).

```python
# apps/workspaces/models.py
from encrypted_fields.fields import EncryptedTextField, EncryptedCharField

class WorkspaceSecret(models.Model):
    workspace = models.ForeignKey(Workspace, related_name="secrets", on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    value = EncryptedTextField()  # chiffré automatiquement
    description = models.CharField(max_length=255, blank=True)
    last_rotated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("workspace", "key")
```

```python
# config/settings/base.py
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY")
# Générer avec : python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Règles impératives :**
- `value` n'est jamais sérialisé dans les réponses API (uniquement `key` et `description`).
- `value` est redacté dans tous les logs (voir `redact_sensitive()` dans 18-securite.md).
- Les secrets ne sont jamais transmis via variables d'environnement Docker si un secret mount est disponible.

---

## Injection dans les conteneurs via Docker Compose secrets

```python
# adapters/docker_adapter.py
def _prepare_secrets(self, service) -> dict:
    """
    Retourne un dictionnaire de secrets à monter comme fichiers dans /run/secrets/.
    Plus sûr que les variables d'environnement (non visibles dans docker inspect).
    """
    secrets = {}
    for ev in service.env_vars.filter(is_secret=True).select_related("secret_ref"):
        if ev.secret_ref:
            secret_name = f"forge_{service.slug}_{ev.key.lower()}"
            secrets[secret_name] = ev.secret_ref.value  # valeur déchiffrée
    return secrets

def run_service(self, service, deployment, image_ref, env_vars, labels) -> docker.models.containers.Container:
    # Env vars non-sensibles
    plain_env = {k: v for k, v in env_vars.items() if not self._is_secret_key(k)}

    # Secrets via tmpfs mount (émulation des Docker secrets en mode standalone)
    secret_mounts = {}
    for key, value in self._prepare_secrets(service).items():
        import tempfile
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".secret", delete=False)
        tmp.write(value)
        tmp.flush()
        secret_mounts[tmp.name] = {"bind": f"/run/secrets/{key}", "mode": "ro"}

    return self.client.containers.run(
        image=image_ref,
        environment=plain_env,
        volumes={**existing_volumes, **secret_mounts},
        # ...
    )
```

---

## API de gestion des secrets

```python
# apps/workspaces/views.py
class WorkspaceSecretViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsWorkspaceAdmin]

    def get_queryset(self):
        return WorkspaceSecret.objects.filter(workspace=self.request.workspace)

    def get_serializer_class(self):
        return WorkspaceSecretWriteSerializer if self.action in ["create", "update"] else WorkspaceSecretReadSerializer


class WorkspaceSecretReadSerializer(serializers.ModelSerializer):
    """Ne retourne jamais la valeur — uniquement le nom et les métadonnées."""
    class Meta:
        model = WorkspaceSecret
        fields = ["id", "key", "description", "last_rotated_at", "created_at"]


class WorkspaceSecretWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceSecret
        fields = ["key", "value", "description"]
        extra_kwargs = {"value": {"write_only": True}}
```

---

## Rotation des secrets

```python
# apps/workspaces/views.py
class RotateSecretView(APIView):
    permission_classes = [IsAuthenticated, IsWorkspaceAdmin]

    def post(self, request, secret_id):
        secret = WorkspaceSecret.objects.get(pk=secret_id, workspace=request.workspace)
        new_value = request.data.get("new_value")
        if not new_value:
            return Response({"error": "new_value required"}, status=400)

        secret.value = new_value
        secret.last_rotated_at = timezone.now()
        secret.save(update_fields=["value", "last_rotated_at"])

        # Déclencher un redéploiement de tous les services qui utilisent ce secret
        from apps.deployments.services import DeploymentService
        for ev in secret.serviceenvvar_set.select_related("service"):
            if ev.service.active_deployment_id is None:
                DeploymentService.create_deployment(
                    service=ev.service,
                    triggered_by=request.user,
                    trigger_source="manual",
                )

        AuditLog.objects.create(
            workspace=request.workspace,
            user=request.user,
            action="secret.rotate",
            resource_type="WorkspaceSecret",
            resource_id=str(secret.pk),
        )
        return Response({"ok": True, "rotated_at": secret.last_rotated_at})
```

---

## V2 — Migration vers HashiCorp Vault KV v2

### Prérequis

```yaml
# infra/docker-compose.platform.yml (ajout V2)
vault:
  image: hashicorp/vault:1.17
  cap_add: [IPC_LOCK]
  environment:
    VAULT_ADDR: "http://0.0.0.0:8200"
    VAULT_DEV_ROOT_TOKEN_ID: "${VAULT_ROOT_TOKEN}"  # dev uniquement
  command: vault server -config=/vault/config/vault.hcl
  volumes:
    - vault-data:/vault/data
    - ./vault/config:/vault/config:ro
  networks:
    - forge-platform
```

### Adapter Vault

```python
# adapters/vault_adapter.py
import hvac
from django.conf import settings


class VaultAdapter:
    def __init__(self):
        self.client = hvac.Client(
            url=settings.VAULT_ADDR,
            token=settings.VAULT_TOKEN,
        )

    def write_secret(self, workspace_slug: str, key: str, value: str) -> None:
        self.client.secrets.kv.v2.create_or_update_secret(
            path=f"{workspace_slug}/{key}",
            mount_point="forge",
            secret={"value": value},
        )

    def read_secret(self, workspace_slug: str, key: str) -> str:
        resp = self.client.secrets.kv.v2.read_secret_version(
            path=f"{workspace_slug}/{key}",
            mount_point="forge",
        )
        return resp["data"]["data"]["value"]

    def delete_secret(self, workspace_slug: str, key: str) -> None:
        self.client.secrets.kv.v2.delete_metadata_and_all_versions(
            path=f"{workspace_slug}/{key}",
            mount_point="forge",
        )
```

### Migration one-shot

```python
# scripts/migrate_secrets_to_vault.py
from apps.workspaces.models import WorkspaceSecret
from adapters.vault_adapter import VaultAdapter

vault = VaultAdapter()
for secret in WorkspaceSecret.objects.all():
    vault.write_secret(
        workspace_slug=secret.workspace.slug,
        key=secret.key,
        value=secret.value,  # déchiffré automatiquement
    )
    print(f"Migrated: {secret.workspace.slug}/{secret.key}")
print("Migration complete. Update VAULT_ENABLED=true in settings before removing encrypted fields.")
```
