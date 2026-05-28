"""
Adapter métriques — lecture Prometheus pour le Monitor Hub et l'Activator.
Implémentation complète dans 17-observabilite.md.
"""
from __future__ import annotations

import logging
import urllib.request
import json

logger = logging.getLogger(__name__)


class MetricsAdapter:
    def __init__(self, prometheus_url: str) -> None:
        self.base_url = prometheus_url.rstrip("/")

    def query(self, promql: str) -> list[dict]:
        encoded = urllib.parse.quote(promql)
        url = f"{self.base_url}/api/v1/query?query={encoded}"
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read())
        return data.get("data", {}).get("result", [])

    def get_cpu_percent(self, container_name: str) -> float | None:
        results = self.query(
            f'rate(container_cpu_usage_seconds_total{{name="{container_name}"}}[5m]) * 100'
        )
        if results:
            return float(results[0]["value"][1])
        return None

    def get_memory_percent(self, container_name: str) -> float | None:
        results = self.query(
            f'container_memory_usage_bytes{{name="{container_name}"}} '
            f'/ container_spec_memory_limit_bytes{{name="{container_name}"}} * 100'
        )
        if results:
            return float(results[0]["value"][1])
        return None

    def get_http_5xx_rate(self, service_slug: str, window: str = "5m") -> float | None:
        results = self.query(
            f'rate(traefik_service_requests_total{{service="{service_slug}",code=~"5.."}}[{window}])'
        )
        if results:
            return float(results[0]["value"][1])
        return None


import urllib.parse  # noqa: E402
