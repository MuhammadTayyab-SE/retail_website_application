from django.shortcuts import render
from django.views.decorators.http import require_safe

from catalog.models import Category


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
