from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone
from .models import Purchase, PurchaseItem
from medicines.models import Medicine
from suppliers.models import Supplier

class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ['supplier', 'invoice_number', 'purchase_date', 'remarks']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'invoice_number': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Enter Invoice Number'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 3, 'placeholder': 'Optional remarks...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only list active suppliers
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)


class PurchaseItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = ['medicine', 'batch_no', 'expiry_date', 'quantity', 'unit_cost']
        widgets = {
            'medicine': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary medicine-select'}),
            'batch_no': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Batch No'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary quantity-input', 'min': 1}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary cost-input', 'min': 0.01, 'step': 0.01}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only list active medicines
        self.fields['medicine'].queryset = Medicine.objects.filter(is_active=True)

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')
        if expiry_date and expiry_date < timezone.now().date():
            raise forms.ValidationError("Expiry date cannot be in the past.")
        return expiry_date

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return quantity

    def clean_unit_cost(self):
        unit_cost = self.cleaned_data.get('unit_cost')
        if unit_cost is not None and unit_cost <= 0:
            raise forms.ValidationError("Unit cost must be greater than zero.")
        return unit_cost


PurchaseItemFormSet = inlineformset_factory(
    Purchase,
    PurchaseItem,
    form=PurchaseItemForm,
    extra=1,
    can_delete=True
)
