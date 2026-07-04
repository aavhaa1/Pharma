from django.contrib import admin
from .models import Category, Medicine


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ("name", "medicine_count", "created_at")
    search_fields = ("name", "description")
    ordering      = ("name",)
    readonly_fields = ("created_at",)

    def medicine_count(self, obj):
        return obj.medicines.count()
    medicine_count.short_description = "# Medicines"


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "category",
        "unit",
        "purchase_price",
        "selling_price",
        "requires_prescription",
        "is_active",
    )
    list_filter   = ("category", "unit", "requires_prescription", "is_active")
    search_fields = ("name", "brand", "description")
    ordering      = ("name",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "brand", "category", "unit", "description")
        }),
        ("Pricing", {
            "fields": ("purchase_price", "selling_price")
        }),
        ("Settings", {
            "fields": ("requires_prescription", "is_active")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
