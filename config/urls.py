from django.http import JsonResponse
from django.urls import path
from django.views.decorators.http import require_safe

from catalog.views import category_list
from config.admin import site


@require_safe
def health(request):
    """Process liveness only: deliberately independent of database availability."""
    response = JsonResponse({"status": "ok"})
    response["Cache-Control"] = "no-store"
    return response


urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", site.urls),
    path("categories/", category_list, name="category-list"),
]
