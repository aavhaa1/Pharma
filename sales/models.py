from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
from medicines.models import Medicine
from inventory.models import Inventory

User = get_user_model()

class Sale(models.Model):
    PAYMENT_METHODS = [
        ('Cash', 'Cash'),
        ('Card', 'Card'),
        ('Mobile Payment', 'Mobile Payment'),
    ]

    invoice_number = models.CharField(max_length=100, unique=True)
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    sale_date = models.DateField(auto_now_add=True)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS, default='Cash')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    cashier = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Sale {self.invoice_number}"

    @classmethod
    def generate_next_invoice_number(cls):
        """
        Generate a sequential invoice number: e.g. INV-00001
        """
        last_sale = cls.objects.all().order_by('id').last()
        if not last_sale:
            return "INV-00001"
        
        # Parse the sequential number from last invoice
        import re
        invoice_num = last_sale.invoice_number
        match = re.search(r'INV-(\d+)', invoice_num)
        if match:
            next_num = int(match.group(1)) + 1
            return f"INV-{next_num:05d}"
        else:
            # Fallback if pattern not matched
            return f"INV-{last_sale.id + 1:05d}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='sale_items')
    inventory_batch = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='sale_items')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def save(self, *args, **kwargs):
        self.total_price = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicine.name} (Qty: {self.quantity}) - {self.sale.invoice_number}"
