import re

from django import forms


class CheckoutForm(forms.Form):
    email = forms.EmailField(
        max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    phone = forms.CharField(
        max_length=30, widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"})
    )
    first_name = forms.CharField(
        max_length=100, widget=forms.TextInput(attrs={"autocomplete": "given-name"})
    )
    last_name = forms.CharField(
        max_length=100, widget=forms.TextInput(attrs={"autocomplete": "family-name"})
    )
    address = forms.CharField(
        max_length=300, widget=forms.TextInput(attrs={"autocomplete": "address-line1"})
    )
    landmark = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"autocomplete": "address-line2"}),
    )
    city = forms.CharField(
        max_length=100, widget=forms.TextInput(attrs={"autocomplete": "address-level2"})
    )
    postal_code = forms.CharField(
        required=False, max_length=20, widget=forms.TextInput(attrs={"autocomplete": "postal-code"})
    )
    notes = forms.CharField(
        required=False, max_length=2000, widget=forms.Textarea(attrs={"rows": 3})
    )
    delivery_method = forms.ChoiceField(
        choices=[("delivery", "Home delivery")], widget=forms.RadioSelect
    )
    payment_method = forms.ChoiceField(choices=(), widget=forms.RadioSelect)
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, policy=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_method"].choices = (
            [("cod", "Cash on delivery — pay when your order arrives")]
            if policy is None or policy.cash_on_delivery
            else []
        )

    def clean_phone(self):
        value = self.cleaned_data["phone"].strip()
        digits = re.sub(r"[\s()+-]", "", value)
        if not digits.isascii() or not digits.isdigit() or not 7 <= len(digits) <= 15:
            raise forms.ValidationError(
                "Enter a valid phone number, including its area or country code."
            )
        return value
