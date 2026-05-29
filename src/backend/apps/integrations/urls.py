from django.urls import path

from .views import GitHubWebhookView

urlpatterns = [
    path("integrations/github/webhook/", GitHubWebhookView.as_view(), name="github-webhook"),
]
