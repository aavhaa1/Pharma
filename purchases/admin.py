from django.contrib import admin
from .models import Purchase, PurchaseItem

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'invoice_number', 'supplier', 'purchase_date', 'total_amount', 'status', 'created_by')
    list_filter = ('status', 'purchase_date', 'supplier')
    search_fields = ('invoice_number', 'supplier__name')
    inlines = [PurchaseItemInline]
    readonly_fields = ('created_at', 'updated_at')
