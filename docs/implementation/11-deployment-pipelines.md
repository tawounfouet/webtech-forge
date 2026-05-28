# 11 — Deployment Pipelines & Gate d'approbation

> **ADR de référence :** ADR-019
> **Dépendances :** 04-modeles-donnees.md, 07-deployment-engine.md

---

## Modèles

```python
# apps/environments/models.py (suite)
from django.conf import settings
from django.db import models


class PromotionRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    source_environment = models.ForeignKey(
        "Environment", related_name="promotions_out", on_delete=models.CASCADE
    )
    target_environment = models.ForeignKey(
        "Environment", related_name="promotions_in", on_delete=models.CASCADE
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    diff_snapshot = models.JSONField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    def is_approved(self) -> bool:
        policy = getattr(self.target_environment, "promotionpolicy", None)
        if not policy or not policy.require_approval:
            return True
        return self.approvals.count() >= policy.min_approvers


class PromotionApproval(models.Model):
    request = models.ForeignKey(PromotionRequest, related_name="approvals", on_delete=models.CASCADE)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    approved_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)

    class Meta:
        unique_together = ("request", "approved_by")
```

---

## Service de promotion

```python
# apps/environments/services.py
from django.utils import timezone
from django.db.models import Q
from .models import Environment, PromotionRequest, PromotionApproval
from apps.deployments.models import Deployment
from apps.services.models import Service, ServiceEnvVar


class PromotionService:
    @staticmethod
    def compute_diff(source: Environment, target: Environment) -> dict:
        diff = {"source": source.slug, "target": target.slug, "services": []}
        for src_service in source.services.prefetch_related("env_vars", "domains"):
            try:
                tgt_service = target.services.get(slug=src_service.slug)
            except Service.DoesNotExist:
                diff["services"].append({
                    "slug": src_service.slug,
                    "change_type": "new",
                })
                continue

            src_deploy = src_service.deployments.filter(status="success").order_by("-finished_at").first()
            tgt_deploy = tgt_service.deployments.filter(status="success").order_by("-finished_at").first()

            src_env = {ev.key: ev.value for ev in src_service.env_vars.filter(is_secret=False)}
            tgt_env = {ev.key: ev.value for ev in tgt_service.env_vars.filter(is_secret=False)}

            changes = {
                "image_ref": {
                    "from": tgt_deploy.image_ref if tgt_deploy else None,
                    "to": src_deploy.image_ref if src_deploy else None,
                },
                "env": {
                    "added": [k for k in src_env if k not in tgt_env],
                    "removed": [k for k in tgt_env if k not in src_env],
                    "modified": [k for k in src_env if k in tgt_env and src_env[k] != tgt_env[k]],
                },
            }
            if any([
                changes["image_ref"]["from"] != changes["image_ref"]["to"],
                changes["env"]["added"],
                changes["env"]["removed"],
                changes["env"]["modified"],
            ]):
                diff["services"].append({"slug": src_service.slug, "changes": changes})

        return diff

    @staticmethod
    def create_request(source: Environment, target: Environment, requested_by) -> PromotionRequest:
        diff = PromotionService.compute_diff(source, target)
        return PromotionRequest.objects.create(
            source_environment=source,
            target_environment=target,
            diff_snapshot=diff,
            requested_by=requested_by,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )

    @staticmethod
    def approve(request: PromotionRequest, approved_by, comment: str = "") -> PromotionRequest:
        PromotionApproval.objects.get_or_create(
            request=request, approved_by=approved_by,
            defaults={"comment": comment},
        )
        if request.is_approved():
            PromotionService.execute(request, approved_by)
        return request

    @staticmethod
    def execute(request: PromotionRequest, executed_by):
        from apps.deployments.services import DeploymentService
        request.status = PromotionRequest.Status.APPROVED
        request.resolved_at = timezone.now()
        request.save(update_fields=["status", "resolved_at"])

        for service_diff in request.diff_snapshot.get("services", []):
            slug = service_diff["slug"]
            try:
                src_service = request.source_environment.services.get(slug=slug)
                tgt_service = request.target_environment.services.get(slug=slug)
            except Service.DoesNotExist:
                continue

            src_deploy = src_service.deployments.filter(status="success").order_by("-finished_at").first()
            if src_deploy:
                new_dep = Deployment.objects.create(
                    service=tgt_service,
                    triggered_by=executed_by,
                    trigger_source="promotion",
                    image_ref=src_deploy.image_ref,
                    commit_sha=src_deploy.commit_sha,
                    phase=Deployment.Phase.GOLD,
                    status=Deployment.Status.PENDING,
                )
                tgt_service.acquire_deploy_lock(new_dep)
                from apps.deployments.tasks import run_deployment_pipeline
                run_deployment_pipeline.apply_async(args=[new_dep.id], queue="deployments")
```

---

## Vues API

```python
# apps/environments/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Environment, PromotionRequest
from .services import PromotionService
from apps.workspaces.permissions import IsOperatorOrAbove, IsWorkspaceAdmin


class EnvironmentPromoteDiffView(APIView):
    """GET /api/v1/environments/{id}/promotion-diff?target={target_id}"""
    permission_classes = [IsAuthenticated, IsOperatorOrAbove]

    def get(self, request, pk):
        source = self._get_env(pk, request.workspace)
        target_id = request.query_params.get("target")
        target = self._get_env(target_id, request.workspace)
        diff = PromotionService.compute_diff(source, target)
        return Response(diff)

    def _get_env(self, pk, workspace):
        try:
            return Environment.objects.get(pk=pk, project__workspace=workspace)
        except Environment.DoesNotExist:
            from django.http import Http404
            raise Http404


class EnvironmentPromoteView(APIView):
    """POST /api/v1/environments/{id}/promote"""
    permission_classes = [IsAuthenticated, IsOperatorOrAbove]

    def post(self, request, pk):
        source = Environment.objects.get(pk=pk, project__workspace=request.workspace)
        target_id = request.data.get("target_environment_id")
        target = Environment.objects.get(pk=target_id, project__workspace=request.workspace)

        promo = PromotionService.create_request(source, target, request.user)

        # Si pas d'approbation requise, exécuter immédiatement
        if not getattr(target, "promotionpolicy", None) or not target.promotionpolicy.require_approval:
            PromotionService.execute(promo, request.user)
            return Response({"status": "executed", "promotion_id": promo.id})

        # Notifier les approbateurs
        _notify_approvers(promo)
        return Response({"status": "pending_approval", "promotion_id": promo.id}, status=status.HTTP_202_ACCEPTED)


class PromotionApproveView(APIView):
    """POST /api/v1/promotions/{id}/approve"""
    permission_classes = [IsAuthenticated, IsWorkspaceAdmin]

    def post(self, request, pk):
        promo = PromotionRequest.objects.get(
            pk=pk,
            target_environment__project__workspace=request.workspace,
            status=PromotionRequest.Status.PENDING,
        )
        comment = request.data.get("comment", "")
        promo = PromotionService.approve(promo, request.user, comment)
        return Response({"status": promo.status, "approvals": promo.approvals.count()})


def _notify_approvers(promo: PromotionRequest):
    policy = getattr(promo.target_environment, "promotionpolicy", None)
    if not policy:
        return
    for channel in policy.notify_channels:
        if channel.get("type") == "email":
            from django.core.mail import send_mail
            send_mail(
                subject=f"[Forge] Promotion approval required: {promo.source_environment.slug} → {promo.target_environment.slug}",
                message=f"Approve at: {channel.get('base_url', '')}/promotions/{promo.id}/",
                from_email="forge@webtech.fr",
                recipient_list=[channel["target"]],
            )
```

---

## Tâche d'expiration des promotions

```python
# apps/environments/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import PromotionRequest


@shared_task
def expire_pending_promotions():
    expired = PromotionRequest.objects.filter(
        status=PromotionRequest.Status.PENDING,
        expires_at__lt=timezone.now(),
    )
    count = expired.update(
        status=PromotionRequest.Status.CANCELLED,
        resolved_at=timezone.now(),
    )
    return f"Cancelled {count} expired promotion requests"
```
