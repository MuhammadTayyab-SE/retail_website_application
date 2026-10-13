from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_safe

from catalog.models import Category, Product, ProductPhoto
from config.admin import site


@require_safe
def home02(request):
    """Keep the captured layout while supplying the live homepage collections."""
    categories = storefront_categories()
    category_ids = {entry["category"].pk for entry in categories}
    top_categories = [entry for entry in categories if entry["category"].parent_id is None]
    parent_category_ids = set(Category.objects.parents().values_list("pk", flat=True))
    product_categories = [
        entry for entry in categories if entry["category"].pk not in parent_category_ids
    ]
    root_categories = {}
    for entry in categories:
        category = entry["category"]
        root_categories[category.pk] = (
            root_categories[category.parent_id] if category.parent_id else category
        )
    catalog_products = (
        Product.objects.visible()
        .filter(category_id__in=category_ids)
        .select_related("category")
        .prefetch_related("photos")
    )
    counts = {
        row["category_id"]: row["total"]
        for row in catalog_products.order_by()
        .values("category_id")
        .annotate(total=Count("pk", distinct=True))
    }
    for entry in reversed(categories):
        category = entry["category"]
        count = counts.get(category.pk, 0)
        entry["product_count"] = count
        if category.parent_id:
            counts[category.parent_id] = counts.get(category.parent_id, 0) + count
    query = request.GET.get("q", "").strip()[:200]
    selected = request.GET.get("category", "").strip()
    selected_id = (
        int(selected) if selected.isascii() and selected.isdigit() and len(selected) < 19 else None
    )
    selected_category = next(
        (entry["category"] for entry in categories if entry["category"].pk == selected_id), None
    )
    products = catalog_products
    if query:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    if selected:
        if selected_category:
            descendants = {selected_category.pk}
            for entry in categories:
                category = entry["category"]
                if category.parent_id in descendants:
                    descendants.add(category.pk)
            products = products.filter(category_id__in=descendants)
        else:
            products = products.none()
    page = Paginator(products, 24).get_page(request.GET.get("page"))
    featured = list(page)
    trending = list(products.order_by(F("created_at").desc(nulls_last=True), "-pk")[:6])
    sale_products = list(products.filter(is_on_sale=True)[:7])
    weekly_deal_products = list(products.filter(is_on_sale=True)[:8])
    top_rated_products = list(products.order_by("?")[:5])
    for product in [
        *featured,
        *trending,
        *sale_products,
        *weekly_deal_products,
        *top_rated_products,
    ]:
        product.homepage_category = root_categories[product.category_id]
    featured_categories = {}
    for product in featured:
        entry = featured_categories.setdefault(
            product.homepage_category.pk, {"category": product.homepage_category, "count": 0}
        )
        entry["count"] += 1
    context = {
        "homepage_categories": top_categories,
        "homepage_top_categories": product_categories,
        "featured_products": featured,
        "featured_categories": list(featured_categories.values()),
        "trending_products": trending,
        "homepage_sale_products": sale_products,
        "weekly_deal_products": weekly_deal_products,
        "homepage_top_rated_products": top_rated_products,
        "page_obj": page,
        "query": query,
        "selected": selected,
        "selected_category": selected_category,
        "invalid_category": bool(selected and not selected_category),
    }
    return render(request, "catalog/home02/home.html", context)


@require_safe
def catalogue_redirect(request):
    """Old saved catalogue links lead to the single current storefront."""
    parameters = request.GET.urlencode()
    target = reverse("home")
    if parameters:
        target += "?" + parameters
    return redirect(target + "#rtsb-container-138192095")


def storefront_categories():
    """Return active, reachable categories, including their breadcrumb paths."""
    children = {}
    for category in Category.objects.all():
        children.setdefault(category.parent_id, []).append(category)
    visible, seen = [], set()
    stack = [(category, []) for category in reversed(children.get(None, []))]
    while stack:
        category, ancestors = stack.pop()
        if not category.is_active or category.pk in seen:
            continue
        seen.add(category.pk)
        path = [*ancestors, category.name]
        visible.append({"category": category, "path": " / ".join(path)})
        stack.extend((child, path) for child in reversed(children.get(category.pk, [])))
    return visible


@require_safe
def public_category_photo(request, pk):
    category = next(
        (entry["category"] for entry in storefront_categories() if entry["category"].pk == pk),
        None,
    )
    if category is None or not category.photo:
        raise Http404
    try:
        content_type = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(
            category.photo.name.rsplit(".", 1)[-1].lower()
        )
        if not content_type:
            raise Http404
        response = FileResponse(category.photo.open("rb"), content_type=content_type)
    except FileNotFoundError as exc:
        raise Http404 from exc
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


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


def serve_product_photo(photo):
    try:
        content_type = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(
            photo.image.name.rsplit(".", 1)[-1].lower()
        )
        if not content_type:
            raise Http404
        response = FileResponse(photo.image.open("rb"), content_type=content_type)
    except FileNotFoundError as exc:
        raise Http404 from exc
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@require_safe
@site.admin_view
def product_photo(request, pk):
    if not (
        request.user.has_perm("catalog.view_product")
        or request.user.has_perm("catalog.change_product")
    ):
        raise PermissionDenied
    return serve_product_photo(get_object_or_404(ProductPhoto, pk=pk))


@require_safe
def product_list(request):
    products = Product.objects.visible().select_related("category").prefetch_related("photos")
    return render(request, "catalog/products.html", {"products": products})


@require_safe
@site.admin_view
def catalog_view(request):
    product_admin = site._registry[Product]
    if not product_admin.has_view_permission(request):
        raise PermissionDenied
    visible_products = Product.objects.visible()
    products = visible_products.select_related("category").prefetch_related("photos")
    query = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    if selected_category:
        products = products.filter(category_id=selected_category)
    context = {
        **site.each_context(request),
        "title": "Catalog",
        "opts": Product._meta,
        "products": products,
        "categories": Category.objects.filter(
            pk__in=visible_products.values("category_id")
        ).order_by("name"),
        "query": query,
        "selected_category": selected_category,
        "can_add_product": product_admin.has_add_permission(request),
        "can_change_product": product_admin.has_change_permission(request),
    }
    return render(request, "catalog/catalog.html", context)


@require_safe
def public_product_photo(request, pk):
    photo = get_object_or_404(ProductPhoto, pk=pk, product__in=Product.objects.visible())
    return serve_product_photo(photo)
