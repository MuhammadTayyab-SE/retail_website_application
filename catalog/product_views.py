from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_safe

from catalog.models import Product
from catalog.views import storefront_categories


@require_safe
def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.visible().select_related("category").prefetch_related("photos", "variants"),
        pk=pk,
    )
    variants = [variant for variant in product.variants.all() if variant.is_active]
    active_ids = {variant.pk for variant in variants}
    photos = [
        {
            "src": reverse("public-product-photo", args=[photo.pk]),
            "alt": photo.alt_text or product.name,
            "variant": str(photo.variant_id or ""),
        }
        for photo in product.photos.all()
        if photo.variant_id is None or photo.variant_id in active_ids
    ]
    options = []
    for variant in variants:
        variant.product = product
        options.append(
            {
                "id": str(variant.pk),
                "sku": variant.sku,
                "label": " / ".join(
                    f"{key.title()}: {value}" for key, value in sorted(variant.attributes.items())
                )
                or variant.sku,
                "price": str(variant.sale_price),
                "regular_price": str(product.price if variant.price is None else variant.price),
                "description": variant.description or product.description,
            }
        )
    if not options:
        options = [
            {
                "id": "",
                "sku": product.sku,
                "label": "Standard",
                "price": str(product.sale_price),
                "regular_price": str(product.price),
                "description": product.description,
            }
        ]
    selected = next(
        (option for option in options if option["id"] == request.GET.get("variant")), options[0]
    )
    selected_photos = [photo for photo in photos if photo["variant"] == selected["id"]]
    selected_photos += [
        photo for photo in photos if not photo["variant"] and photo not in selected_photos
    ]
    categories = storefront_categories()
    return render(
        request,
        "catalog/product/page.html",
        {
            "product": product,
            "options": options,
            "selected_option": selected,
            "selected_photos": selected_photos,
            "has_variants": bool(variants),
            "homepage_categories": [
                entry for entry in categories if entry["category"].parent_id is None
            ],
            "product_data": {
                "options": options,
                "photos": photos,
                "selected": selected["id"],
                "name": product.name,
                "stock": product.quantity,
                "product": str(product.pk),
            },
        },
    )
