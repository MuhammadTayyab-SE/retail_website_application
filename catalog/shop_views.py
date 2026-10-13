from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import render
from django.views.decorators.http import require_safe

from catalog.models import Product
from catalog.shop_forms import ShopFilterForm
from catalog.views import storefront_categories


@require_safe
def shop(request):
    categories = storefront_categories()
    top_categories = [entry for entry in categories if entry["category"].parent_id is None]
    roots = {}
    for entry in categories:
        category = entry["category"]
        roots[category.pk] = roots[category.parent_id] if category.parent_id else category
    products = (
        Product.objects.visible()
        .filter(category_id__in=roots)
        .with_selling_price()
        .select_related("category")
        .prefetch_related("photos")
    )
    counts = {}
    for row in products.order_by().values("category_id").annotate(total=Count("pk", distinct=True)):
        root_id = roots[row["category_id"]].pk
        counts[root_id] = counts.get(root_id, 0) + row["total"]
    for entry in top_categories:
        entry["product_count"] = counts.get(entry["category"].pk, 0)
    form = ShopFilterForm(request.GET, categories=top_categories)
    values = form.cleaned_data if form.is_valid() else {}
    if form.errors:
        products = products.none()
    else:
        if values["q"]:
            products = products.filter(
                Q(name__icontains=values["q"]) | Q(sku__icontains=values["q"])
            )
        if values["category"]:
            selected = set(values["category"])
            category_ids = [pk for pk, root in roots.items() if str(root.pk) in selected]
            products = products.filter(category_id__in=category_ids)
        if values["unit"]:
            products = products.filter(unit__in=values["unit"])
        if values["min_price"] is not None:
            products = products.filter(selling_price__gte=values["min_price"])
        if values["max_price"] is not None:
            products = products.filter(selling_price__lte=values["max_price"])
        if values["sale"]:
            products = products.filter(is_on_sale=values["sale"] == "sale")
        if values["stock"] == "in":
            products = products.filter(quantity__gt=0)
        elif values["stock"] == "out":
            products = products.filter(quantity=0)
    ordering = {
        "latest": [F("created_at").desc(nulls_last=True), "-pk"],
        "price": ["selling_price", "pk"],
        "price-desc": ["-selling_price", "pk"],
        "name": ["name", "pk"],
    }
    products = products.order_by(*ordering.get(values.get("sort"), ["name", "pk"]))
    page = Paginator(products, int(values.get("per_page") or 16)).get_page(request.GET.get("page"))
    for product in page:
        product.homepage_category = roots[product.category_id]
    parameters = request.GET.copy()
    parameters.pop("page", None)
    context = {
        "homepage_categories": top_categories,
        "page_obj": page,
        "filter_form": form,
        "selected_categories": request.GET.getlist("category"),
        "selected_units": request.GET.getlist("unit"),
        "unit_choices": Product.Unit.choices,
        "query": request.GET.get("q", "")[:200],
        "selected": request.GET.get("category", ""),
        "filters_query": parameters.urlencode(),
        "list_view": values.get("view") == "list",
    }
    return render(request, "catalog/shop/page.html", context)
