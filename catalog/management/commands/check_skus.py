from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef
from django.db.models.functions import Lower, Trim

from catalog.models import ProductVariant, SkuIdentifier


class Command(BaseCommand):
    help = "Read-only check that current variant SKUs match the permanent issuance registry."

    def handle(self, **options):
        issued = SkuIdentifier.objects.filter(
            variant_id=OuterRef("pk"),
            variant_key=OuterRef("pk"),
            product_id=OuterRef("product_id"),
            product_key=OuterRef("product_id"),
            code=Lower(Trim(OuterRef("sku"))),
        )
        if (
            ProductVariant.objects.alias(registered=Exists(issued))
            .filter(registered=False)
            .exists()
        ):
            raise CommandError(
                "Variant SKU ownership does not match the permanent registry; no data changed."
            )
        self.stdout.write(
            f"SKU registry check passed: {ProductVariant.objects.count()} live variants; "
            f"{SkuIdentifier.objects.count()} reserved codes."
        )
