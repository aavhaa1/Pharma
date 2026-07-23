from django.db import models


class Category(models.Model):
    """
    Groups medicines into logical categories (e.g. Antibiotics, Analgesics).
    Used for filtering and reporting across Inventory, Purchases, and Sales.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Category Name",
        help_text="e.g. Antibiotics, Analgesics, Vitamins"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Optional description of what this category covers."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active",
        help_text="Inactive categories are hidden from selection and list views."
    )

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]


    def __str__(self):
        return self.name


class Medicine(models.Model):
    """
    Core medicine catalog. Referenced by Inventory (stock), Purchases
    (restocking), and Sales (transactions) via ForeignKey.
    """

    UNIT_CHOICES = [
        ("tablet",  "Tablet"),
        ("capsule", "Capsule"),
        ("syrup",   "Syrup (ml)"),
        ("injection","Injection (ml)"),
        ("cream",   "Cream (g)"),
        ("drops",   "Drops (ml)"),
        ("sachet",  "Sachet"),
        ("other",   "Other"),
    ]

    # --- Core Identity ---
    name = models.CharField(
        max_length=200,
        verbose_name="Medicine Name",
        help_text="Generic or brand name of the medicine."
    )
    brand = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Brand Name",
        help_text="Manufacturer brand name, if different from generic name."
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicines",
        verbose_name="Category"
    )

    # --- Classification ---
    unit = models.CharField(
        max_length=20,
        choices=UNIT_CHOICES,
        default="tablet",
        verbose_name="Unit of Measurement",
        help_text="How this medicine is measured/dispensed."
    )
    requires_prescription = models.BooleanField(
        default=False,
        verbose_name="Requires Prescription",
        help_text="If True, cashiers must request a prescription before selling."
    )

    # --- Pricing ---
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Purchase Price (Rs.)",
        help_text="Cost price per unit paid to supplier."
    )
    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Selling Price (Rs.)",
        help_text="Retail price per unit charged to customers."
    )

    # --- Description ---
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description / Usage",
        help_text="Optional notes on usage, dosage, or side effects."
    )

    minimum_stock_level = models.PositiveIntegerField(
        default=10,
        verbose_name="Minimum Stock Level",
        help_text="The threshold level below which stock is considered low."
    )

    # --- Status & Timestamps ---
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active",
        help_text="Inactive medicines are hidden from sales and inventory views."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Last Updated"
    )

    class Meta:
        verbose_name = "Medicine"
        verbose_name_plural = "Medicines"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_unit_display()})"

    @property
    def profit_margin(self):
        """Returns the profit per unit in Rs."""
        return self.selling_price - self.purchase_price

    @property
    def available_stock(self):
        if hasattr(self, '_available_stock'):
            return self._available_stock
        from django.utils import timezone
        from django.db.models import Sum
        today = timezone.now().date()
        return self.inventory_batches.filter(
            expiry_date__gte=today
        ).aggregate(total=Sum('quantity'))['total'] or 0

    @available_stock.setter
    def available_stock(self, value):
        self._available_stock = value

    @property
    def is_out_of_stock(self):
        return self.available_stock == 0

    @property
    def is_low_stock(self):
        available = self.available_stock
        return 0 < available <= self.minimum_stock_level

