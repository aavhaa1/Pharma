from django.shortcuts import render
from django.views.generic import TemplateView, ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Sum, Count, Avg, F, Q
from decimal import Decimal
from datetime import timedelta
import calendar

from accounts.utils import is_admin, is_pharmacist
from medicines.models import Medicine, Category
from inventory.models import Inventory
from purchases.models import Purchase, PurchaseItem
from sales.models import Sale
from suppliers.models import Supplier

from .utils import get_filtered_data, generate_csv, generate_excel, generate_pdf_report

User = get_user_model()

class AdminOrPharmacistOnlyMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or is_admin(user) or is_pharmacist(user))


class ReportsDashboardView(LoginRequiredMixin, AdminOrPharmacistOnlyMixin, TemplateView):
    template_name = 'reports/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        
        # 1. Total Sales Today
        context['total_sales_today'] = Sale.objects.filter(sale_date=today).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        # 2. Total Sales This Month & Monthly Revenue
        context['total_sales_month'] = Sale.objects.filter(sale_date__gte=start_of_month).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        context['monthly_revenue'] = context['total_sales_month']
        
        # 3. Total Purchases
        context['total_purchases'] = Purchase.objects.filter(status='Received').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        # 4. Total Medicines
        context['total_medicines'] = Medicine.objects.filter(is_active=True).count()
        # 5. Total Suppliers
        context['total_suppliers'] = Supplier.objects.filter(is_active=True).count()
        
        # 6. Current Inventory Value
        context['inventory_value'] = Inventory.objects.aggregate(
            total=Sum(F('quantity') * F('medicine__purchase_price'))
        )['total'] or Decimal('0.00')
        
        # 7. Low Stock Medicines count
        context['low_stock_medicines_count'] = Medicine.objects.annotate(
            total_stock=Sum('inventory_batches__quantity')
        ).filter(Q(total_stock__lte=F('minimum_stock_level')) | Q(total_stock__isnull=True)).count()
        
        # 8. Expired Medicines count
        context['expired_medicines_count'] = Inventory.objects.filter(expiry_date__lt=today).count()
        # 9. Medicines Expiring Within 30 Days count
        context['expiring_soon_count'] = Inventory.objects.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=30)
        ).count()
        
        return context


class SalesReportView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'reports/sales_report.html'
    context_object_name = 'sales'
    paginate_by = 20

    def get_queryset(self):
        return get_filtered_data('sales', self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        
        # Calculations/Aggregations
        aggregations = qs.aggregate(
            total_sum=Sum('total_amount'),
            total_count=Count('id'),
            avg_val=Avg('total_amount')
        )
        context['total_sales'] = aggregations['total_sum'] or Decimal('0.00')
        context['total_revenue'] = context['total_sales']
        context['num_transactions'] = aggregations['total_count'] or 0
        context['avg_sale_value'] = aggregations['avg_val'] or Decimal('0.00')
        
        # Filters context
        context['cashiers'] = User.objects.filter(groups__name__in=['Admin', 'Pharmacist', 'Cashier']).distinct()
        return context


class PurchaseReportView(LoginRequiredMixin, AdminOrPharmacistOnlyMixin, ListView):
    model = Purchase
    template_name = 'reports/purchase_report.html'
    context_object_name = 'purchases'
    paginate_by = 20

    def get_queryset(self):
        return get_filtered_data('purchases', self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        
        aggregations = qs.aggregate(
            total_sum=Sum('total_amount'),
            total_count=Count('id')
        )
        context['total_purchases'] = aggregations['total_count'] or 0
        context['total_purchase_value'] = aggregations['total_sum'] or Decimal('0.00')
        
        context['suppliers'] = Supplier.objects.filter(is_active=True)
        return context


class InventoryReportView(LoginRequiredMixin, AdminOrPharmacistOnlyMixin, ListView):
    model = Inventory
    template_name = 'reports/inventory_report.html'
    context_object_name = 'inventory_items'
    paginate_by = 20

    def get_queryset(self):
        return get_filtered_data('inventory', self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        
        context['total_inventory_qty'] = qs.aggregate(total=Sum('quantity'))['total'] or 0
        context['inventory_value'] = qs.aggregate(
            total_val=Sum(F('quantity') * F('medicine__purchase_price'))
        )['total_val'] or Decimal('0.00')
        
        context['medicines'] = Medicine.objects.filter(is_active=True)
        context['categories'] = Category.objects.filter(is_active=True)
        context['suppliers'] = Supplier.objects.filter(is_active=True)
        return context


class MedicineReportView(LoginRequiredMixin, AdminOrPharmacistOnlyMixin, ListView):
    model = Medicine
    template_name = 'reports/medicine_report.html'
    context_object_name = 'medicines'
    paginate_by = 20

    def get_queryset(self):
        return get_filtered_data('medicines', self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        
        context['total_medicines'] = qs.count()
        # total stock across matching medicines
        context['total_stock'] = Inventory.objects.filter(medicine__in=qs).aggregate(total=Sum('quantity'))['total'] or 0
        
        # Add supplier context to each medicine row (last supplier)
        for med in context['medicines']:
            last_item = med.purchase_items.filter(purchase__status='Received').order_by('-purchase__purchase_date').first()
            med.last_supplier = last_item.purchase.supplier.name if last_item else 'N/A'
            
        context['categories'] = Category.objects.filter(is_active=True)
        context['suppliers'] = Supplier.objects.filter(is_active=True)
        return context


class SupplierReportView(LoginRequiredMixin, AdminOrPharmacistOnlyMixin, ListView):
    model = Supplier
    template_name = 'reports/supplier_report.html'
    context_object_name = 'suppliers'
    paginate_by = 20

    def get_queryset(self):
        return get_filtered_data('suppliers', self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        
        context['total_suppliers'] = qs.count()
        context['active_suppliers'] = qs.filter(is_active=True).count()
        
        # Populate aggregation metrics for list
        for s in context['suppliers']:
            s.num_medicines = PurchaseItem.objects.filter(purchase__supplier=s, purchase__status='Received').values('medicine').distinct().count()
            s.num_purchases = Purchase.objects.filter(supplier=s, status='Received').count()
            s.total_value = Purchase.objects.filter(supplier=s, status='Received').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
            
        return context


class LowStockReportView(LoginRequiredMixin, AdminOrPharmacistOnlyMixin, ListView):
    model = Medicine
    template_name = 'reports/low_stock_report.html'
    context_object_name = 'medicines'
    paginate_by = 20

    def get_queryset(self):
        return get_filtered_data('low-stock', self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch supplier for low stock rows
        for med in context['medicines']:
            last_item = med.purchase_items.filter(purchase__status='Received').order_by('-purchase__purchase_date').first()
            med.last_supplier = last_item.purchase.supplier.name if last_item else 'N/A'
        return context


class ExpiryReportView(LoginRequiredMixin, AdminOrPharmacistOnlyMixin, ListView):
    model = Inventory
    template_name = 'reports/expiry_report.html'
    context_object_name = 'inventory_items'
    paginate_by = 20

    def get_queryset(self):
        return get_filtered_data('expiry', self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        
        # Annotate days remaining
        for item in context['inventory_items']:
            days = (item.expiry_date - today).days
            item.days_remaining = days
            # Fetch supplier
            last_item = PurchaseItem.objects.filter(medicine=item.medicine, batch_no=item.batch_no, purchase__status='Received').first()
            item.supplier_name = last_item.purchase.supplier.name if last_item else 'N/A'
            
        return context


class RevenueReportView(LoginRequiredMixin, AdminOrPharmacistOnlyMixin, TemplateView):
    template_name = 'reports/revenue_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        
        # Revenue calculations
        context['daily_revenue'] = Sale.objects.filter(sale_date=today).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        context['weekly_revenue'] = Sale.objects.filter(sale_date__gte=today - timedelta(days=7)).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        context['monthly_revenue'] = Sale.objects.filter(sale_date__gte=today - timedelta(days=30)).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        context['yearly_revenue'] = Sale.objects.filter(sale_date__gte=today - timedelta(days=365)).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

        # Chart.js Monthly Sales and Monthly Revenue data for current year
        monthly_sales_list = [0] * 12
        monthly_revenue_list = [0.0] * 12
        
        sales_by_month = Sale.objects.filter(sale_date__year=today.year).values('sale_date__month').annotate(
            count=Count('id'),
            revenue=Sum('total_amount')
        )
        
        for record in sales_by_month:
            m = record['sale_date__month']
            if 1 <= m <= 12:
                monthly_sales_list[m - 1] = record['count']
                monthly_revenue_list[m - 1] = float(record['revenue'] or 0.0)
                
        context['monthly_sales_data'] = monthly_sales_list
        context['monthly_revenue_data'] = monthly_revenue_list
        context['months_labels'] = [calendar.month_name[i] for i in range(1, 13)]
        
        return context


# --- Dynamic Read-only Exports ---

class ExportCSVView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        report_type = request.GET.get('report_type')
        # Apply Cashier security check
        if report_type != 'sales' and not (request.user.is_superuser or is_admin(request.user) or is_pharmacist(request.user)):
            raise PermissionDenied
            
        queryset = get_filtered_data(report_type, request.GET)
        if queryset is None:
            raise PermissionDenied
            
        return generate_csv(report_type, queryset)


class ExportExcelView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        report_type = request.GET.get('report_type')
        if report_type != 'sales' and not (request.user.is_superuser or is_admin(request.user) or is_pharmacist(request.user)):
            raise PermissionDenied
            
        queryset = get_filtered_data(report_type, request.GET)
        if queryset is None:
            raise PermissionDenied
            
        return generate_excel(report_type, queryset)


class ExportPDFView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        report_type = request.GET.get('report_type')
        if report_type != 'sales' and not (request.user.is_superuser or is_admin(request.user) or is_pharmacist(request.user)):
            raise PermissionDenied
            
        queryset = get_filtered_data(report_type, request.GET)
        if queryset is None:
            raise PermissionDenied
            
        return generate_pdf_report(report_type, queryset)
