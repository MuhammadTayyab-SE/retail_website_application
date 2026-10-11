from django.db import migrations


def enforce_inactive_category_hierarchy(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Product = apps.get_model("catalog", "Product")

    categories = {
        category_id: {"parent_id": parent_id, "is_active": is_active}
        for category_id, parent_id, is_active in Category.objects.values_list(
            "pk", "parent_id", "is_active"
        )
    }
    inactive = {category_id for category_id, data in categories.items() if not data["is_active"]}
    changed = True
    while changed:
        descendants = {
            category_id for category_id, data in categories.items() if data["parent_id"] in inactive
        }
        expanded = inactive | descendants
        changed = expanded != inactive
        inactive = expanded

    if inactive:
        Category.objects.filter(pk__in=inactive).update(is_active=False)
        Product.objects.filter(category_id__in=inactive).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0009_product_sale_fields")]

    operations = [
        migrations.RunPython(enforce_inactive_category_hierarchy, migrations.RunPython.noop)
    ]
