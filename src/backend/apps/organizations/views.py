from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Organization
from .serializers import OrganizationSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer
    lookup_field = "slug"

    def get_queryset(self):
        from apps.workspaces.models import WorkspaceMember
        org_ids = (
            WorkspaceMember.objects.filter(user=self.request.user)
            .values_list("workspace__organization_id", flat=True)
            .distinct()
        )
        return Organization.objects.filter(pk__in=org_ids)
