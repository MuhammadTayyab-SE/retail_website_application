"""Synthetic catalog builders using the current variant-owned schema."""

from catalog.models import Product, ProductPhoto


def new_product(*, sku="", unit="each", barcode="", package_content="", **fields):
    product = Product(**fields)
    product._default_variant_initial = {
        "sku": sku,
        "inventory_unit": unit,
        "barcode": barcode,
        "package_content": package_content,
    }
    return product


def create_product(**fields):
    product = new_product(**fields)
    product.save()
    return product


def create_products(products):
    for product in products:
        product.save()
    return products


def create_photo(*, product=None, variant=None, **fields):
    if variant is None:
        variant = product.default_variant
    return ProductPhoto.objects.create(variant=variant, **fields)
