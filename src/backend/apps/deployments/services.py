from __future__ import annotations

from django.core.exceptions import ValidationError

from .models import Deployment, RollbackRecord


class DeploymentService:
    """
    Service métier pour la création et le contrôle des déploiements.
    Encapsule la logique qui ne doit pas vivre dans les vues DRF ni dans
    les tâches Celery (séparation des responsabilités).
    """

    @staticmethod
    def create_deployment(
        service,
        triggered_by,
        trigger_source: str = "manual",
    ) -> Deployment:
        """
        Crée un Deployment, acquiert le lock sur le Service, et enqueue
        le pipeline Medallion dans la queue Celery "deployments".
        """
        from .tasks import run_deployment_pipeline

        deployment = Deployment.objects.create(
            service=service,
            triggered_by=triggered_by,
            trigger_source=trigger_source,
            status=Deployment.Status.PENDING,
            phase=Deployment.Phase.BRONZE,
        )
        try:
            service.acquire_deploy_lock(deployment)
        except ValidationError:
            deployment.delete()
            raise

        run_deployment_pipeline.apply_async(
            args=[deployment.id],
            queue="deployments",
        )
        return deployment

    @staticmethod
    def rollback(deployment: Deployment, triggered_by) -> Deployment:
        """
        Crée un déploiement de rollback vers le dernier SUCCESS connu.
        Démarre directement en phase GOLD (image déjà buildée et pushée).
        """
        from .tasks import run_deployment_pipeline

        last_success = (
            Deployment.objects.filter(
                service=deployment.service,
                status=Deployment.Status.SUCCESS,
            )
            .exclude(pk=deployment.pk)
            .order_by("-finished_at")
            .first()
        )
        if not last_success:
            raise ValueError("Aucun déploiement en succès disponible pour le rollback")

        new_deployment = Deployment.objects.create(
            service=deployment.service,
            triggered_by=triggered_by,
            trigger_source=Deployment.TriggerSource.MANUAL,
            image_ref=last_success.image_ref,
            commit_sha=last_success.commit_sha,
            status=Deployment.Status.PENDING,
            # Saute Bronze/Silver — l'image est déjà dans le registry
            phase=Deployment.Phase.GOLD,
        )
        RollbackRecord.objects.create(
            deployment=deployment,
            rolled_back_to=last_success,
            triggered_by=triggered_by,
            trigger_source=RollbackRecord.TriggerSource.MANUAL,
        )
        run_deployment_pipeline.apply_async(
            args=[new_deployment.id],
            queue="deployments",
        )
        return new_deployment

    @staticmethod
    def trigger_auto_deploy(repo, branch: str) -> list[Deployment]:
        """
        Déclenché par le webhook GitHub. Lance un déploiement sur chaque
        service d'un environnement dont auto_deploy_branch correspond à la branche pushée.
        """
        from apps.environments.models import Environment

        deployed = []
        for env in Environment.objects.filter(
            project__repositories=repo,
            auto_deploy_branch=branch,
        ):
            for service in env.services.filter(
                runtime__in=[
                    "dockerfile",
                    "compose",
                ]
            ):
                try:
                    d = DeploymentService.create_deployment(
                        service=service,
                        triggered_by=None,
                        trigger_source=Deployment.TriggerSource.WEBHOOK,
                    )
                    deployed.append(d)
                except (ValidationError, Exception):
                    # Un service déjà en cours de déploiement est ignoré silencieusement
                    pass
        return deployed
