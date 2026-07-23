from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Sum, Count, F, Q
from django.db.models.functions import Coalesce
from datetime import timedelta
from decimal import Decimal
import json

from inventory.models import Inventory
from purchases.models import Purchase
from suppliers.models import Supplier
from medicines.models import Medicine, Category
from sales.models import Sale


@login_required
def home(request):
    today = timezone.now().date()
    
    # Redirect role-specific users to their dedicated dashboards
    if request.user.groups.filter(name='Pharmacist').exists() and not request.user.is_superuser:
        return redirect('pharmacist:dashboard')
    
    if request.user.groups.filter(name='Cashier').exists() and not request.user.is_superuser:
        return redirect('cashier:cashier_dashboard')

    # ── 1. KPI Summary Metrics ──
    total_sales_today = Sale.objects.filter(sale_date=today).aggregate(
        total=Coalesce(Sum('total_amount'), Decimal('0.00'))
    )['total']
    
    total_revenue = Sale.objects.aggregate(
        total=Coalesce(Sum('total_amount'), Decimal('0.00'))
    )['total']
    
    total_inventory_quantity = Inventory.objects.aggregate(
        total=Coalesce(Sum('quantity'), 0)
    )['total']
    
    inventory_value = Inventory.objects.aggregate(
        total_val=Coalesce(Sum(F('quantity') * F('medicine__purchase_price')), Decimal('0.00'))
    )['total_val']

    total_medicines = Medicine.objects.filter(is_active=True).count()
    total_categories = Category.objects.filter(is_active=True).count()
    total_suppliers = Supplier.objects.filter(is_active=True).count()
    total_purchases = Purchase.objects.count()

    # Stock alerts
    low_stock_medicines = Inventory.objects.select_related('medicine').filter(
        quantity__lte=F('medicine__minimum_stock_level'),
        quantity__gt=0,
        expiry_date__gte=today
    ).order_by('quantity')[:6]

    out_of_stock_medicines = Medicine.objects.annotate(
        total_stock=Coalesce(
            Sum('inventory_batches__quantity', filter=Q(inventory_batches__expiry_date__gte=today)),
            0
        )
    ).filter(total_stock=0, is_active=True)[:6]

    expiring_soon_medicines = Inventory.objects.select_related('medicine').filter(
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=30),
        quantity__gt=0
    ).order_by('expiry_date')[:6]

    # Recent Data Tables
    recent_sales = Sale.objects.select_related('cashier').order_by('-created_at')[:5]
    recent_purchases = Purchase.objects.select_related('supplier').order_by('-created_at')[:5]

    # ── 2. Chart Data ──
    # A. Monthly Sales Trend (Last 6 months)
    monthly_labels = []
    monthly_sales_data = []
    for i in range(5, -1, -1):
        m_date = today.replace(day=1) - timedelta(days=30 * i)
        start_d = m_date.replace(day=1)
        end_d = (start_d + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        val = Sale.objects.filter(sale_date__range=[start_d, end_d]).aggregate(
            total=Coalesce(Sum('total_amount'), Decimal('0.00'))
        )['total']
        monthly_labels.append(start_d.strftime("%b %Y"))
        monthly_sales_data.append(float(val))

    # B. Stock Status Distribution
    out_of_stock_cnt = Medicine.objects.annotate(
        total_stock=Coalesce(
            Sum('inventory_batches__quantity', filter=Q(inventory_batches__expiry_date__gte=today)),
            0
        )
    ).filter(total_stock=0, is_active=True).count()

    low_stock_cnt = Medicine.objects.annotate(
        total_stock=Coalesce(
            Sum('inventory_batches__quantity', filter=Q(inventory_batches__expiry_date__gte=today)),
            0
        )
    ).filter(
        total_stock__gt=0,
        total_stock__lte=F('minimum_stock_level'),
        is_active=True
    ).count()

    in_stock_cnt = max(0, total_medicines - out_of_stock_cnt - low_stock_cnt)

    # C. Category Distribution
    categories = Category.objects.annotate(
        total_stock=Coalesce(Sum('medicines__inventory_batches__quantity'), 0)
    ).filter(is_active=True, total_stock__gt=0)[:8]
    cat_labels = [c.name for c in categories]
    cat_data = [c.total_stock for c in categories]

    context = {
        "total_sales_today": total_sales_today,
        "total_revenue": total_revenue,
        "total_inventory_quantity": total_inventory_quantity,
        "inventory_value": inventory_value,
        "total_medicines": total_medicines,
        "total_categories": total_categories,
        "total_suppliers": total_suppliers,
        "total_purchases": total_purchases,
        "low_stock_medicines": low_stock_medicines,
        "out_of_stock_medicines": out_of_stock_medicines,
        "expiring_soon_medicines": expiring_soon_medicines,
        "recent_sales": recent_sales,
        "recent_purchases": recent_purchases,
        "monthly_labels_json": json.dumps(monthly_labels),
        "monthly_sales_json": json.dumps(monthly_sales_data),
        "stock_status_data_json": json.dumps([in_stock_cnt, low_stock_cnt, out_of_stock_cnt]),
        "cat_labels_json": json.dumps(cat_labels),
        "cat_data_json": json.dumps(cat_data),
    }
    return render(request, "dashboard/home.html", context)