from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from medicines.models import Medicine

User = get_user_model()

class Inventory(models.Model):
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
        verbose_name = "Inventory"
        verbose_name_plural = "Inventories"
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

    @property
    def is_low_stock(self):
        return not self.is_expired and 0 < self.quantity < 50


    @property
    def is_out_of_stock(self):
        return self.quantity == 0

    @property
    def status(self):
        if self.is_out_of_stock:
            return "Out of Stock"
        elif self.is_expired:
            return "Expired"
        elif self.is_expiring_soon:
            return "Expiring Soon"
        elif self.is_low_stock:
            return "Low Stock"
        else:
            return "Normal"

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

    def save_with_history(self, user, action, quantity_changed, reason, quantity_before=0):
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
            reason=reason
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
        Inventory,
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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Logged At")

    class Meta:
        verbose_name = "Inventory History"
        verbose_name_plural = "Inventory Histories"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.inventory.medicine.name} - {self.action} by {self.user.username}"
