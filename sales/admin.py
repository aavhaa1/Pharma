from django.contrib import admin
from .models import Sale, SaleItem

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'invoice_number', 'customer_name', 'sale_date', 'payment_method', 'total_amount', 'cashier')
    list_filter = ('payment_method', 'sale_date', 'cashier')
    search_fields = ('invoice_number', 'customer_name')
    inlines = [SaleItemInline]
    readonly_fields = ('created_at',)
