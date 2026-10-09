from django.http import JsonResponse
from django.urls import path
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    """Process liveness only: deliberately independent of database availability."""
    response = JsonResponse({"status": "ok"})
    response["Cache-Control"] = "no-store"
    return response


urlpatterns = [path("health/", health, name="health")]
