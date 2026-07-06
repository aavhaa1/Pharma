from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def home(request):
    from django.utils import timezone
    from django.db.models import Sum, F
    from datetime import timedelta
    from inventory.models import Inventory

    today = timezone.now().date()
    
    total_inventory_quantity = Inventory.objects.aggregate(total=Sum('quantity'))['total'] or 0
    total_inventory_batches = Inventory.objects.count()
    low_stock_count = Inventory.objects.filter(quantity__lte=F('medicine__minimum_stock_level')).count()
    expired_medicines_count = Inventory.objects.filter(expiry_date__lt=today).count()
    expiring_soon_count = Inventory.objects.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30)).count()

    context = {
        "total_inventory_quantity": total_inventory_quantity,
        "total_inventory_batches": total_inventory_batches,
        "low_stock_count": low_stock_count,
        "expired_medicines_count": expired_medicines_count,
        "expiring_soon_count": expiring_soon_count,
    }
    return render(request, "dashboard/home.html", context)