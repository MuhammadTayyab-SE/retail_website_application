from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe

from catalog.models import Category
from config.admin import site


@require_safe
def category_list(request):
    categories = list(Category.objects.all())
    children = {}
    for category in categories:
        children.setdefault(category.parent_id, []).append(category)
    visible = []
    stack = [(category, []) for category in reversed(children.get(None, []))]
    while stack:
        category, ancestors = stack.pop()
        if not category.is_active:
            continue
        path = [*ancestors, category.name]
        visible.append({"category": category, "path": " / ".join(path)})
        stack.extend((child, path) for child in reversed(children.get(category.pk, [])))
    return render(request, "catalog/categories.html", {"categories": visible})


@require_safe
@site.admin_view
def category_photo(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if not site._registry[Category].has_view_permission(request, category):
        raise PermissionDenied
    if not category.photo:
        raise Http404
    try:
        extension = category.photo.name.rsplit(".", 1)[-1].lower()
        content_type = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(
            extension
        )
        if not content_type:
            raise Http404
        response = FileResponse(category.photo.open("rb"), content_type=content_type)
    except FileNotFoundError as exc:
        raise Http404 from exc
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
