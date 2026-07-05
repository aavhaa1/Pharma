from django.db import models

class Supplier(models.Model):
    """
    Model representing a medicine supplier/vendor.
    """
    name = models.CharField(max_length=255, unique=True, help_text="Unique name of the supplier company.")
    contact_person = models.CharField(max_length=255, blank=True, null=True, help_text="Primary contact person name.")
    phone = models.CharField(max_length=50, blank=True, null=True, help_text="Contact phone number.")
    email = models.EmailField(blank=True, null=True, help_text="Contact email address.")
    address = models.TextField(blank=True, null=True, help_text="Physical or billing address.")
    is_active = models.BooleanField(default=True, help_text="Whether this supplier is currently active.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
