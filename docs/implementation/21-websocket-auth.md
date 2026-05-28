# 21 — WebSocket & Streaming de logs

> **ADR de référence :** ADR-004
> **Dépendances :** 03-backend-django.md, 04-modeles-donnees.md

---

## Architecture dual-canal

| Canal | Technologie | Sémantique | Usage |
|---|---|---|---|
| **Éphémère** | WebSocket + Redis Channel Layer | At-most-once | Affichage temps réel pendant le déploiement |
| **Persistant** | `DeploymentEvent` (PostgreSQL) + Loki | At-least-once | Historique des logs, reconnexion, audit |

Le WebSocket ne remplace pas la persistance — il la complète. Si la connexion WebSocket est coupée, le client peut récupérer les events manquants via `GET /api/v1/deployments/{id}/events`.

---

## Consumer Django Channels avec auth par premier frame

```python
# apps/deployments/consumers.py
import asyncio
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class DeploymentLogConsumer(AsyncWebsocketConsumer):
    AUTH_TIMEOUT_SECONDS = 5

    async def connect(self):
        self.authenticated = False
        self.user = None
        self.deployment_id = self.scope["url_route"]["kwargs"]["deployment_id"]
        self.group_name = f"deployment_{self.deployment_id}"

        await self.accept()

        # Lance un timeout d'authentification
        self._auth_timeout_task = asyncio.create_task(
            self._close_if_unauthenticated()
        )

    async def _close_if_unauthenticated(self):
        await asyncio.sleep(self.AUTH_TIMEOUT_SECONDS)
        if not self.authenticated:
            await self.close(code=4001)

    async def disconnect(self, close_code):
        if hasattr(self, "_auth_timeout_task"):
            self._auth_timeout_task.cancel()
        if self.authenticated:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            await self.close(code=4002)
            return

        # Premier message = authentification
        if data.get("type") == "auth" and not self.authenticated:
            token = data.get("token", "")
            user = await self._validate_token(token)
            if user and await self._can_view_deployment(user, self.deployment_id):
                self.authenticated = True
                self.user = user
                if hasattr(self, "_auth_timeout_task"):
                    self._auth_timeout_task.cancel()
                await self.channel_layer.group_add(self.group_name, self.channel_name)
                # Envoyer les events déjà en base (reconnexion)
                await self._send_historical_events()
                await self.send(json.dumps({"type": "auth.success"}))
            else:
                await self.send(json.dumps({"type": "auth.error", "message": "Invalid token or insufficient permissions"}))
                await self.close(code=4001)

    async def log_message(self, event):
        """Reçoit les messages du channel layer et les forward au client WebSocket."""
        if self.authenticated:
            await self.send(text_data=json.dumps({
                "type": "log",
                "phase": event.get("phase"),
                "message": event.get("message"),
                "level": event.get("level", "info"),
            }))

    @database_sync_to_async
    def _validate_token(self, token: str):
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        from apps.accounts.models import User
        try:
            validated = AccessToken(token)
            return User.objects.get(pk=validated["user_id"])
        except (InvalidToken, TokenError, User.DoesNotExist):
            return None

    @database_sync_to_async
    def _can_view_deployment(self, user, deployment_id: str) -> bool:
        from apps.deployments.models import Deployment
        from apps.workspaces.models import WorkspaceMember
        try:
            deployment = Deployment.objects.select_related(
                "service__environment__project__workspace"
            ).get(pk=deployment_id)
            workspace = deployment.service.environment.project.workspace
            return WorkspaceMember.objects.filter(
                workspace=workspace, user=user
            ).exists()
        except Deployment.DoesNotExist:
            return False

    @database_sync_to_async
    def _get_historical_events(self):
        from apps.deployments.models import DeploymentEvent
        return list(
            DeploymentEvent.objects.filter(deployment_id=self.deployment_id)
            .order_by("emitted_at")
            .values("phase", "message", "level")
        )

    async def _send_historical_events(self):
        events = await self._get_historical_events()
        for event in events:
            await self.send(json.dumps({
                "type": "log",
                "phase": event["phase"],
                "message": event["message"],
                "level": event["level"],
                "historical": True,
            }))
```

---

## Routing WebSocket

```python
# apps/deployments/routing.py
from django.urls import re_path
from .consumers import DeploymentLogConsumer

websocket_urlpatterns = [
    re_path(r"^ws/logs/(?P<deployment_id>\d+)/$", DeploymentLogConsumer.as_asgi()),
]
```

---

## Diffusion depuis les workers Celery

Les workers Celery émettent des events vers le channel layer Redis pour que le consumer les reçoive en temps réel :

```python
# apps/deployments/tasks.py
def _emit(deployment, phase, message, level="info"):
    """Persiste l'event ET le diffuse en temps réel."""
    from apps.deployments.models import DeploymentEvent
    DeploymentEvent.objects.create(
        deployment=deployment,
        phase=phase,
        message=message,
        level=level,
    )

    # Diffusion asynchrone vers le channel layer
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"deployment_{deployment.id}",
        {
            "type": "log.message",
            "phase": phase,
            "message": message,
            "level": level,
        },
    )
```

---

## Logs des services en production (non-déploiement)

Les logs des services en production (conteneurs actifs) sont accessibles via :

```
GET /api/v1/services/{id}/logs?tail=100&since=3600
```

```python
# apps/services/views.py
class ServiceLogsView(APIView):
    def get(self, request, pk):
        service = get_object_or_404(
            Service,
            pk=pk,
            environment__project__workspace=request.workspace,
        )
        from adapters.docker_adapter import DockerAdapter
        docker = DockerAdapter()
        tail = int(request.query_params.get("tail", 100))
        since = int(request.query_params.get("since", 3600))
        logs = docker.get_container_logs(service, since=since, tail=tail)
        return Response({"logs": logs})
```

---

## Tests du consumer

```python
# tests/test_ws_consumer.py
import pytest
from channels.testing import WebsocketCommunicator
from config.asgi import application


@pytest.mark.asyncio
async def test_ws_rejects_without_auth():
    communicator = WebsocketCommunicator(application, "/ws/logs/1/")
    connected, _ = await communicator.connect()
    assert connected

    # Attendre le timeout d'auth
    await asyncio.sleep(6)
    # La connexion doit être fermée avec le code 4001
    assert await communicator.receive_nothing()


@pytest.mark.asyncio
async def test_ws_accepts_valid_token(valid_jwt_token, deployment_factory):
    deployment = await deployment_factory()
    communicator = WebsocketCommunicator(application, f"/ws/logs/{deployment.id}/")
    connected, _ = await communicator.connect()

    await communicator.send_json_to({"type": "auth", "token": valid_jwt_token})
    response = await communicator.receive_json_from()
    assert response["type"] == "auth.success"
    await communicator.disconnect()
```
