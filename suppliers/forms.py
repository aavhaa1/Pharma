import re
from django import forms
from .models import Supplier

# Consistent Bootstrap styling classes matching medicines/forms.py
TEXT_INPUT_CLASS = "form-control"
TEXTAREA_CLASS = "form-control"

class SupplierForm(forms.ModelForm):
    """
    Form for creating and editing suppliers.
    """
    class Meta:
        model = Supplier
        fields = [
            "name",
            "contact_person",
            "phone",
            "email",
            "address",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "e.g. Acme Pharmaceuticals Ltd.",
                "autofocus": True,
            }),
            "contact_person": forms.TextInput(attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "e.g. John Doe",
            }),
            "phone": forms.TextInput(attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "e.g. +1 123-456-7890 or 9841XXXXXX",
            }),
            "email": forms.EmailInput(attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "e.g. supplier@example.com",
            }),
            "address": forms.Textarea(attrs={
                "class": TEXTAREA_CLASS,
                "placeholder": "Physical or office address...",
                "rows": 3,
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
        }
        labels = {
            "name": "Supplier Name",
            "contact_person": "Contact Person (optional)",
            "phone": "Phone Number (optional)",
            "email": "Email Address (optional)",
            "address": "Address (optional)",
            "is_active": "Active Status",
        }
        help_texts = {
            "name": "Must be unique. e.g. 'Global Pharma Dist.'.",
            "phone": "Allows numbers, spaces, dashes, parentheses, and '+'.",
        }

    def clean_name(self):
        """Supplier name is required and must be unique (case-insensitive)."""
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Supplier name is required.")
        
        # Check case-insensitive uniqueness
        qs = Supplier.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise forms.ValidationError(f"A supplier named \"{name}\" already exists.")
        return name

    def clean_phone(self):
        """Allow common phone formats or empty/None."""
        phone = self.cleaned_data.get("phone", "")
        if phone:
            phone = phone.strip()
            if len(phone) > 20:
                raise forms.ValidationError("Phone number cannot exceed 20 characters.")
            # Allow digits, spaces, hyphens, plus sign, and parentheses
            phone_pattern = r'^[+\d\s\-\(\)]+$'
            if not re.match(phone_pattern, phone):
                raise forms.ValidationError("Phone number should only contain numbers, spaces, dashes, parentheses, and '+'.")
        return phone

    def clean_email(self):
        """Validate email format if provided."""
        email = self.cleaned_data.get("email", "")
        if email:
            email = email.strip().lower()
            # Check for duplicate email among active suppliers (excluding self on edit)
            qs = Supplier.objects.filter(email__iexact=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"A supplier with email \"{email}\" already exists.")
        return email
