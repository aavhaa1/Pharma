from django.contrib import admin
from .models import Inventory, InventoryHistory

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ["id", "medicine", "batch_no", "expiry_date", "quantity", "location", "created_at", "updated_at"]
    list_filter = ["expiry_date", "medicine"]
    search_fields = ["batch_no", "medicine__name"]


@admin.register(InventoryHistory)
class InventoryHistoryAdmin(admin.ModelAdmin):
    list_display = ["id", "inventory", "user", "action", "quantity_before", "quantity_after", "quantity_changed", "reason", "created_at"]
    list_filter = ["action", "user"]
    search_fields = ["inventory__medicine__name", "reason"]
