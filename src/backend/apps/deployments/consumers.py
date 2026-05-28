import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Deployment, DeploymentEvent


class DeploymentLogConsumer(AsyncWebsocketConsumer):
    async def connect(self) -> None:
        self.deployment_id = self.scope["url_route"]["kwargs"]["deployment_id"]
        self.group_name = f"deployment_{self.deployment_id}"

        if not self.scope["user"].is_authenticated:
            await self.close(code=4001)
            return

        if not await self._has_access():
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self._send_history()

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def deployment_log(self, event: dict) -> None:
        await self.send(text_data=json.dumps(event["data"]))

    @database_sync_to_async
    def _has_access(self) -> bool:
        from apps.workspaces.models import WorkspaceMember

        try:
            deployment = Deployment.objects.select_related(
                "service__environment__project__workspace"
            ).get(pk=self.deployment_id)
            workspace = deployment.service.environment.project.workspace
            return WorkspaceMember.objects.filter(
                workspace=workspace, user=self.scope["user"]
            ).exists()
        except Deployment.DoesNotExist:
            return False

    @database_sync_to_async
    def _send_history(self) -> None:
        events = DeploymentEvent.objects.filter(deployment_id=self.deployment_id).values(
            "phase", "message", "level", "emitted_at"
        )
        for event in events:
            event["emitted_at"] = event["emitted_at"].isoformat()
            self.send(text_data=json.dumps(event))
