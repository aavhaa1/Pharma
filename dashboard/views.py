from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def home(request):
    from django.utils import timezone
    from django.db.models import Sum, F
    from datetime import timedelta
    from decimal import Decimal
    from inventory.models import Inventory
    from purchases.models import Purchase
    from suppliers.models import Supplier
    from medicines.models import Medicine

    today = timezone.now().date()
    
    total_inventory_quantity = Inventory.objects.aggregate(total=Sum('quantity'))['total'] or 0
    total_inventory_batches = Inventory.objects.count()
    low_stock_count = Inventory.objects.filter(quantity__lte=F('medicine__minimum_stock_level')).count()
    expired_medicines_count = Inventory.objects.filter(expiry_date__lt=today).count()
    expiring_soon_count = Inventory.objects.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30)).count()

    total_purchases = Purchase.objects.count()
    total_suppliers = Supplier.objects.filter(is_active=True).count()
    total_medicines = Medicine.objects.filter(is_active=True).count()

    # Calculate inventory valuation
    inventory_value = Inventory.objects.aggregate(
        total_val=Sum(F('quantity') * F('medicine__purchase_price'))
    )['total_val'] or Decimal('0.00')

    context = {
        "total_inventory_quantity": total_inventory_quantity,
        "total_inventory_batches": total_inventory_batches,
        "low_stock_count": low_stock_count,
        "expired_medicines_count": expired_medicines_count,
        "expiring_soon_count": expiring_soon_count,
        "total_purchases": total_purchases,
        "total_suppliers": total_suppliers,
        "total_medicines": total_medicines,
        "inventory_value": inventory_value,
    }
    return render(request, "dashboard/home.html", context)