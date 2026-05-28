from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ServiceTemplateViewSet

router = DefaultRouter()
router.register("templates", ServiceTemplateViewSet, basename="servicetemplate")

urlpatterns = [path("", include(router.urls))]
