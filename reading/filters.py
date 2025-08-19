from django_filters.rest_framework import DjangoFilterBackend

class SafeDjangoFilterBackend(DjangoFilterBackend):
    """
    DRF's OpenAPI schema still looks for `get_schema_operation_parameters`.
    New django-filter versions (like 25.x) don't provide it anymore.
    This shim returns an empty list so schema generation won't crash.
    """
    def get_schema_operation_parameters(self, view):
        return []