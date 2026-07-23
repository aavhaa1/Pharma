from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Sum, Count, F, Q
from datetime import timedelta
import json
from decimal import Decimal

from medicines.models import Medicine, Category
from inventory.models import Inventory
from purchases.models import Purchase
from suppliers.models import Supplier


class PharmacistRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Restricts access to users in the Pharmacist group (or Superusers).
    """
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or
            user.groups.filter(name='Pharmacist').exists()
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()


class PharmacistDashboardView(PharmacistRequiredMixin, TemplateView):
    template_name = 'pharmacist/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        
        # Summary Cards
        context['total_medicines'] = Medicine.objects.filter(is_active=True).count()
        context['total_categories'] = Category.objects.count()
        context['total_suppliers'] = Supplier.objects.filter(is_active=True).count()
        context['total_inventory_items'] = Inventory.objects.aggregate(total=Sum('quantity'))['total'] or 0

        # Notifications
        context['low_stock_medicines'] = Inventory.objects.select_related('medicine').filter(
            quantity__lte=F('medicine__minimum_stock_level'),
            quantity__gt=0,
            expiry_date__gte=today
        ).order_by('quantity')[:8]
        
        from django.db.models.functions import Coalesce
        context['out_of_stock_medicines'] = Medicine.objects.annotate(
            total_stock=Coalesce(
                Sum('inventory_batches__quantity', filter=Q(inventory_batches__expiry_date__gte=today)),
                0
            )
        ).filter(total_stock=0, is_active=True)[:8]

        context['expiring_medicines'] = Inventory.objects.select_related('medicine').filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=30),
            quantity__gt=0
        ).order_by('expiry_date')[:8]

        # Recent Activity
        context['recent_purchases'] = Purchase.objects.select_related('supplier').order_by('-created_at')[:5]
        context['recently_added_medicines'] = Medicine.objects.order_by('-created_at')[:5]
        
        # Purchases Today
        purchases_today = Purchase.objects.filter(purchase_date=today)
        context['today_purchases_count'] = purchases_today.count()
        context['today_purchases_value'] = purchases_today.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

        # --- Chart Data ---
        # 1. Monthly Purchases (last 6 months)
        monthly_purchases_labels = []
        monthly_purchases_data = []
        for i in range(5, -1, -1):
            month_date = today.replace(day=1) - timedelta(days=30 * i)
            start_date = month_date.replace(day=1)
            end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            total = Purchase.objects.filter(purchase_date__range=[start_date, end_date]).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
            monthly_purchases_labels.append(start_date.strftime("%b %Y"))
            monthly_purchases_data.append(float(total))
            
        context['monthly_purchases_labels'] = json.dumps(monthly_purchases_labels)
        context['monthly_purchases_data'] = json.dumps(monthly_purchases_data)

        # 2. Inventory Distribution by Category
        categories = Category.objects.annotate(total_stock=Sum('medicines__inventory_batches__quantity')).filter(total_stock__gt=0)
        category_labels = [c.name for c in categories]
        category_data = [c.total_stock for c in categories]
        
        context['category_labels'] = json.dumps(category_labels)
        context['category_data'] = json.dumps(category_data)

        # 3. Stock Status (In Stock vs Low Stock vs Out of Stock)
        total_meds = Medicine.objects.filter(is_active=True).count()
        out_of_stock = Medicine.objects.annotate(
            total_stock=Coalesce(
                Sum('inventory_batches__quantity', filter=Q(inventory_batches__expiry_date__gte=today)),
                0
            )
        ).filter(total_stock=0, is_active=True).count()
        low_stock = Medicine.objects.annotate(
            total_stock=Coalesce(
                Sum('inventory_batches__quantity', filter=Q(inventory_batches__expiry_date__gte=today)),
                0
            )
        ).filter(total_stock__gt=0, total_stock__lte=F('minimum_stock_level'), is_active=True).count()
        in_stock = total_meds - out_of_stock - low_stock
        
        context['stock_status_labels'] = json.dumps(['In Stock', 'Low Stock', 'Out of Stock'])
        context['stock_status_data'] = json.dumps([in_stock, low_stock, out_of_stock])

        return context
