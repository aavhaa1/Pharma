from django import forms
from django.utils import timezone
from medicines.models import Medicine
from .models import Inventory, InventoryHistory

TEXT_INPUT_CLASS    = "form-control"
SELECT_CLASS        = "form-select"
NUMBER_INPUT_CLASS  = "form-control"
DATE_INPUT_CLASS    = "form-control"

class InventoryForm(forms.ModelForm):
    """
    Form for adding stock to the inventory.
    Used by Admin and Pharmacist roles.
    """
    class Meta:
        model = Inventory
        fields = ["medicine", "batch_no", "expiry_date", "quantity", "location"]
        widgets = {
            "medicine": forms.Select(attrs={
                "class": SELECT_CLASS,
            }),
            "batch_no": forms.TextInput(attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "e.g. BATCH1024",
            }),
            "expiry_date": forms.DateInput(attrs={
                "class": DATE_INPUT_CLASS,
                "type": "date",
            }),
            "quantity": forms.NumberInput(attrs={
                "class": NUMBER_INPUT_CLASS,
                "placeholder": "e.g. 50",
                "min": "1",
            }),
            "location": forms.TextInput(attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Optional: e.g. Shelf A, Room 2",
            }),
        }
        labels = {
            "medicine": "Medicine",
            "batch_no": "Batch Number",
            "expiry_date": "Expiry Date",
            "quantity": "Quantity",
            "location": "Storage Location (optional)",
        }
        help_texts = {
            "batch_no": "Enter unique batch identifier.",
            "expiry_date": "Date must be today or in the future.",
            "quantity": "Must be greater than 0.",
        }

    def clean_quantity(self):
        qty = self.cleaned_data.get("quantity")
        if qty is None or qty <= 0:
            raise forms.ValidationError("Quantity must be greater than 0.")
        return qty

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get("expiry_date")
        if expiry_date and expiry_date < timezone.now().date():
            raise forms.ValidationError("Expiry date must be today or in the future.")
        return expiry_date


class StockAdjustmentForm(forms.ModelForm):
    """
    Form for manually adjusting inventory stock level.
    Used by Admin and Pharmacist roles.
    """
    ADJUSTMENT_CHOICES = [
        ("Increase", "Increase Stock"),
        ("Decrease", "Decrease Stock"),
    ]
    adjustment_type = forms.ChoiceField(
        choices=ADJUSTMENT_CHOICES,
        label="Adjustment Type",
        widget=forms.Select(attrs={"class": SELECT_CLASS})
    )

    class Meta:
        model = InventoryHistory
        fields = ["inventory", "quantity_changed", "reason"]
        labels = {
            "inventory": "Inventory Batch",
            "quantity_changed": "Adjustment Quantity",
            "reason": "Reason",
        }
        widgets = {
            "inventory": forms.Select(attrs={"class": SELECT_CLASS}),
            "quantity_changed": forms.NumberInput(attrs={
                "class": NUMBER_INPUT_CLASS,
                "min": "1",
                "placeholder": "e.g. 10",
            }),
            "reason": forms.TextInput(attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "e.g. Damaged, Correction, Manual Adjustment",
            }),
        }
        help_texts = {
            "quantity_changed": "Enter the positive quantity to change the stock by.",
            "reason": "Explain the need for this adjustment (e.g. Correction, Damaged).",
        }

    def __init__(self, *args, **kwargs):
        self.inventory = kwargs.pop("inventory", None)
        super().__init__(*args, **kwargs)
        if self.inventory:
            self.fields["inventory"].initial = self.inventory
            self.fields["inventory"].queryset = Inventory.objects.filter(pk=self.inventory.pk)
            self.fields["inventory"].widget.attrs["readonly"] = "readonly"
            self.fields["inventory"].widget.attrs["style"] = "pointer-events: none; opacity: 0.8;"
        else:
            self.fields["inventory"].queryset = Inventory.objects.all()

    def clean_quantity_changed(self):
        qty = self.cleaned_data.get("quantity_changed")
        if qty is None or qty <= 0:
            raise forms.ValidationError("Adjustment quantity must be greater than 0.")
        return qty

    def clean(self):
        cleaned_data = super().clean()
        adjustment_type = cleaned_data.get("adjustment_type")
        quantity_changed = cleaned_data.get("quantity_changed")
        inventory = cleaned_data.get("inventory") or self.inventory

        if inventory and adjustment_type == "Decrease" and quantity_changed:
            if inventory.quantity - quantity_changed < 0:
                raise forms.ValidationError("Stock cannot become negative.")
        return cleaned_data
