from rest_framework.routers import DefaultRouter

from .views import MonitorSnapshotViewSet

router = DefaultRouter()
router.register("monitor", MonitorSnapshotViewSet, basename="monitor")

urlpatterns = router.urls
