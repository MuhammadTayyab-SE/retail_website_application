from django.http import JsonResponse
from django.urls import path
from django.views.decorators.http import require_safe

from catalog.views import (
    catalog_view,
    category_list,
    category_photo,
    product_list,
    product_photo,
    public_product_photo,
)
from config.admin import site


@require_safe
def health(request):
    """Process liveness only: deliberately independent of database availability."""
    response = JsonResponse({"status": "ok"})
    response["Cache-Control"] = "no-store"
    return response


urlpatterns = [
    path("health/", health, name="health"),
    path("admin/category-photo/<int:pk>/", category_photo, name="category-photo"),
    path("admin/product-photo/<int:pk>/", product_photo, name="product-photo"),
    path("admin/catalog/view/", catalog_view, name="catalog-view"),
    path("admin/", site.urls),
    path("categories/", category_list, name="category-list"),
    path("products/", product_list, name="product-list"),
    path("products/photos/<int:pk>/", public_product_photo, name="public-product-photo"),
]
