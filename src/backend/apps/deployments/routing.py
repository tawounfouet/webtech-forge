from django.urls import re_path

from .consumers import DeploymentLogConsumer

websocket_urlpatterns = [
    re_path(r"^ws/logs/(?P<deployment_id>\d+)/$", DeploymentLogConsumer.as_asgi()),
]
