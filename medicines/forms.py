from django import forms
from .models import Category, Medicine


# ─────────────────────────────────────────────
# Shared CSS classes for consistent styling
# ─────────────────────────────────────────────
TEXT_INPUT_CLASS    = "form-control"
TEXTAREA_CLASS      = "form-control"
SELECT_CLASS        = "form-select"
CHECKBOX_CLASS      = "form-check-input"
NUMBER_INPUT_CLASS  = "form-control"


class CategoryForm(forms.ModelForm):
    """
    Form for creating and editing medicine categories.
    Used by Admin role only.
    """

    class Meta:
        model  = Category
        fields = ["name", "description", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class":       TEXT_INPUT_CLASS,
                "placeholder": "e.g. Antibiotics, Analgesics, Vitamins",
                "autofocus":   True,
            }),
            "description": forms.Textarea(attrs={
                "class":       TEXTAREA_CLASS,
                "placeholder": "Optional: briefly describe this category.",
                "rows":        3,
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": CHECKBOX_CLASS,
            }),
        }
        labels = {
            "name":        "Category Name",
            "description": "Description (optional)",
            "is_active":   "Active (visible in dropdowns)",
        }
        help_texts = {
            "name":        "Must be unique. e.g. 'Antibiotics'.",
            "description": "Used internally to clarify which medicines belong here.",
            "is_active":   "Uncheck to deactivate this category without deleting its medicines.",
        }


    def clean_name(self):
        """Ensure category name is unique (case-insensitive)."""
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Category name is required.")
        qs = Category.objects.filter(name__iexact=name)
        # Exclude self when editing (update case)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f"A category named \"{name}\" already exists."
            )
        return name


class MedicineForm(forms.ModelForm):
    """
    Form for creating and editing medicines.
    Used by Admin and Pharmacist roles.
    """

    class Meta:
        model  = Medicine
        fields = [
            "name",
            "brand",
            "category",
            "unit",
            "requires_prescription",
            "purchase_price",
            "selling_price",
            "minimum_stock_level",
            "description",
            "is_active",
        ]
        widgets = {
            # --- Identity ---
            "name": forms.TextInput(attrs={
                "class":       TEXT_INPUT_CLASS,
                "placeholder": "e.g. Paracetamol 500mg",
                "autofocus":   True,
            }),
            "brand": forms.TextInput(attrs={
                "class":       TEXT_INPUT_CLASS,
                "placeholder": "e.g. Panadol (leave blank if generic)",
            }),
            "category": forms.Select(attrs={
                "class": SELECT_CLASS,
            }),
            "unit": forms.Select(attrs={
                "class": SELECT_CLASS,
            }),

            # --- Pricing ---
            "purchase_price": forms.NumberInput(attrs={
                "class":       NUMBER_INPUT_CLASS,
                "placeholder": "0.00",
                "step":        "0.01",
                "min":         "0.01",
            }),
            "selling_price": forms.NumberInput(attrs={
                "class":       NUMBER_INPUT_CLASS,
                "placeholder": "0.00",
                "step":        "0.01",
                "min":         "0.01",
            }),

            # --- Description ---
            "description": forms.Textarea(attrs={
                "class":       TEXTAREA_CLASS,
                "placeholder": "Optional: usage notes, dosage, side effects.",
                "rows":        4,
            }),

            "minimum_stock_level": forms.NumberInput(attrs={
                "class":       NUMBER_INPUT_CLASS,
                "placeholder": "10",
                "min":         "0",
            }),

            # --- Boolean Flags ---
            "requires_prescription": forms.CheckboxInput(attrs={
                "class": CHECKBOX_CLASS,
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": CHECKBOX_CLASS,
            }),
        }
        labels = {
            "name":                  "Medicine Name",
            "brand":                 "Brand Name (optional)",
            "category":              "Category",
            "unit":                  "Unit of Measurement",
            "requires_prescription": "Requires Prescription",
            "purchase_price":        "Purchase Price (Rs.)",
            "selling_price":         "Selling Price (Rs.)",
            "minimum_stock_level":   "Minimum Stock Level",
            "description":           "Description / Usage (optional)",
            "is_active":             "Active (visible to staff)",
        }
        help_texts = {
            "name":                  "Generic drug name. Must be unique.",
            "brand":                 "Manufacturer brand if different from generic.",
            "unit":                  "How this medicine is dispensed per unit.",
            "requires_prescription": "If checked, a valid prescription is required before sale.",
            "purchase_price":        "Cost paid to the supplier per unit.",
            "selling_price":         "Retail price charged to customers per unit.",
            "minimum_stock_level":   "The threshold level below which stock is considered low.",
            "is_active":             "Uncheck to hide this medicine from sales and inventory without deleting it.",
        }

    # ── Field-level validation ────────────────────────────────────────────

    def clean_name(self):
        """Name is required and must be unique (case-insensitive)."""
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Medicine name is required.")
        qs = Medicine.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f"A medicine named \"{name}\" already exists."
            )
        return name

    def clean_purchase_price(self):
        """Purchase price must be greater than zero."""
        price = self.cleaned_data.get("purchase_price")
        if price is not None and price <= 0:
            raise forms.ValidationError(
                "Purchase price must be greater than 0."
            )
        return price

    def clean_selling_price(self):
        """Selling price must be greater than zero."""
        price = self.cleaned_data.get("selling_price")
        if price is not None and price <= 0:
            raise forms.ValidationError(
                "Selling price must be greater than 0."
            )
        return price

    # ── Cross-field validation ────────────────────────────────────────────

    def clean(self):
        """
        Cross-field validation:
        Selling price should not be less than purchase price.
        A warning-style validation is enforced here — staff cannot accidentally
        sell below cost, which would indicate a data entry error.
        """
        cleaned_data   = super().clean()
        purchase_price = cleaned_data.get("purchase_price")
        selling_price  = cleaned_data.get("selling_price")

        if purchase_price and selling_price:
            if selling_price < purchase_price:
                self.add_error(
                    "selling_price",
                    "Selling price cannot be less than the purchase price "
                    f"(Rs. {purchase_price}). Please check the pricing."
                )
        return cleaned_data
