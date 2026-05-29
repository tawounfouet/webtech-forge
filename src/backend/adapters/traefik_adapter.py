"""
Adapter Traefik — génération des labels Docker pour le routing HTTP/HTTPS (blue/green).
"""
from __future__ import annotations


class TraefikAdapter:
    # ── Pipeline interface ────────────────────────────────────────────────────

    @classmethod
    def generate_labels(cls, service, deployment) -> dict[str, str]:
        """
        Génère les labels Docker Traefik pour un déploiement blue/green.
        Les labels sont appliqués au conteneur au moment du `docker run`.
        """
        domain = service.domains.filter(tls_enabled=True).first() or service.domains.first()
        hostname = domain.hostname if domain else f"{service.slug}.forge.local"
        tls = domain.tls_enabled if domain else False
        return cls().build_labels(
            service_slug=service.slug,
            hostname=hostname,
            internal_port=service.internal_port,
            tls_enabled=tls,
        )

    # ── Docker label builders ─────────────────────────────────────────────────

    def build_labels(
        self,
        service_slug: str,
        hostname: str,
        internal_port: int,
        tls_enabled: bool = True,
        network: str = "traefik-public",
    ) -> dict[str, str]:
        router = service_slug.replace("_", "-")
        labels: dict[str, str] = {
            "traefik.enable": "true",
            f"traefik.http.routers.{router}.rule": f"Host(`{hostname}`)",
            f"traefik.http.services.{router}.loadbalancer.server.port": str(internal_port),
            "traefik.docker.network": network,
        }
        if tls_enabled:
            labels[f"traefik.http.routers.{router}.entrypoints"] = "websecure"
            labels[f"traefik.http.routers.{router}.tls.certresolver"] = "letsencrypt"
        else:
            labels[f"traefik.http.routers.{router}.entrypoints"] = "web"
        return labels

    def build_blue_green_labels(
        self,
        service_slug: str,
        hostname: str,
        active_color: str,
        internal_port: int,
    ) -> dict[str, str]:
        """Labels pour un déploiement blue/green — switche le backend actif."""
        router = service_slug.replace("_", "-")
        container_name = f"{service_slug}-{active_color}"
        labels = self.build_labels(service_slug, hostname, internal_port)
        labels[f"traefik.http.services.{router}.loadbalancer.server.url"] = (
            f"http://{container_name}:{internal_port}"
        )
        return labels
