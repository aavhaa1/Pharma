from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from medicines.models import Medicine

User = get_user_model()

class Inventory(models.Model):
    """
    Model representing aggregated stock for a specific medicine.
    """
    medicine = models.OneToOneField(
        Medicine,
        on_delete=models.CASCADE,
        related_name="inventory_record",
        verbose_name="Medicine"
    )
    current_stock = models.PositiveIntegerField(
        default=0,
        verbose_name="Current Stock"
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inventory"
        verbose_name_plural = "Inventories"
        ordering = ["medicine__name"]

    def __str__(self):
        return f"{self.medicine.name} - Stock: {self.current_stock}"

    @property
    def status(self):
        if self.current_stock == 0:
            return "Out of Stock"
        elif self.current_stock <= self.medicine.minimum_stock_level:
            return "Low Stock"
        else:
            return "Normal"

    def update_stock(self):
        """
        Recalculates current_stock based on unexpired InventoryBatch quantities.
        """
        today = timezone.now().date()
        total = self.medicine.inventory_batches.filter(
            expiry_date__gte=today
        ).aggregate(total_qty=models.Sum('quantity'))['total_qty'] or 0
        self.current_stock = total
        self.save()


class InventoryBatch(models.Model):
    """
    Model representing specific stock batches of a medicine.
    """
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name="inventory_batches",
        verbose_name="Medicine"
    )
    batch_no = models.CharField(
        max_length=100,
        verbose_name="Batch Number"
    )
    expiry_date = models.DateField(
        verbose_name="Expiry Date"
    )
    quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantity"
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Storage Location",
        help_text="Optional physical location (e.g. Shelf A, Room 2)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inventory Batch"
        verbose_name_plural = "Inventory Batches"
        ordering = ["expiry_date"]

    def __str__(self):
        return f"{self.medicine.name} (Batch: {self.batch_no})"

    @property
    def is_expired(self):
        return self.expiry_date < timezone.now().date()

    @property
    def is_expiring_soon(self):
        today = timezone.now().date()
        return not self.is_expired and self.expiry_date <= today + timedelta(days=30)

    def clean(self):
        super().clean()
        if self.quantity < 0:
            raise ValidationError({"quantity": "Quantity cannot be negative."})
        if self.pk is None:
            if self.expiry_date and self.expiry_date < timezone.now().date():
                raise ValidationError({"expiry_date": "Expiry date cannot be in the past when creating new stock."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def save_with_history(self, user, action, quantity_changed, reason, quantity_before=0, notes=None):
        """
        Helper method to save the inventory record and automatically log history.
        """
        self.save()
        InventoryHistory.objects.create(
            inventory=self,
            user=user,
            action=action,
            quantity_before=quantity_before,
            quantity_after=self.quantity,
            quantity_changed=quantity_changed,
            reason=reason,
            notes=notes
        )


class InventoryHistory(models.Model):
    """
    Audit log tracking all changes to inventory stock.
    """
    ACTION_CHOICES = [
        ("Added", "Added"),
        ("Adjusted", "Adjusted"),
        ("Removed", "Removed"),
        ("Expired", "Expired"),
    ]

    inventory = models.ForeignKey(
        InventoryBatch,
        on_delete=models.CASCADE,
        related_name="history_logs",
        verbose_name="Inventory Batch"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="inventory_actions",
        verbose_name="Performed By"
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name="Action"
    )
    quantity_before = models.IntegerField(verbose_name="Quantity Before")
    quantity_after = models.IntegerField(verbose_name="Quantity After")
    quantity_changed = models.IntegerField(verbose_name="Quantity Changed")
    reason = models.CharField(
        max_length=255,
        verbose_name="Reason"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes / Remarks"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Logged At")

    class Meta:
        verbose_name = "Inventory History"
        verbose_name_plural = "Inventory Histories"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.inventory.medicine.name} - {self.action} by {self.user.username}"
