"""
Adapter Traefik — génération des labels Docker pour le routing HTTP/HTTPS.
Implémentation complète dans 14-traefik-routing.md.
"""
from __future__ import annotations


class TraefikAdapter:
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
