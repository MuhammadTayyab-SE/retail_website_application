from django import forms

from catalog.models import Product


class ShopFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=200, label="Search products")
    category = forms.MultipleChoiceField(required=False)
    unit = forms.MultipleChoiceField(required=False, choices=Product.Unit.choices)
    min_price = forms.DecimalField(
        required=False, min_value=0, max_digits=12, decimal_places=2, label="Minimum price"
    )
    max_price = forms.DecimalField(
        required=False, min_value=0, max_digits=12, decimal_places=2, label="Maximum price"
    )
    sale = forms.ChoiceField(
        required=False,
        choices=[("", "All products"), ("sale", "On sale"), ("regular", "Regular price")],
    )
    stock = forms.ChoiceField(
        required=False,
        choices=[("", "Any availability"), ("in", "In stock"), ("out", "Out of stock")],
    )
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Default sorting"),
            ("latest", "Sort by latest"),
            ("price", "Price: low to high"),
            ("price-desc", "Price: high to low"),
            ("name", "Product name: A to Z"),
        ],
    )
    view = forms.ChoiceField(required=False, choices=[("grid", "Grid"), ("list", "List")])

    def __init__(self, *args, categories, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].choices = [
            (str(entry["category"].pk), entry["category"].name) for entry in categories
        ]

    def clean(self):
        values = super().clean()
        minimum, maximum = values.get("min_price"), values.get("max_price")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise forms.ValidationError("Minimum price must not exceed maximum price.")
        return values
