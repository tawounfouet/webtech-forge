from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EnvironmentViewSet

router = DefaultRouter()
router.register("environments", EnvironmentViewSet, basename="environment")

urlpatterns = [path("", include(router.urls))]
