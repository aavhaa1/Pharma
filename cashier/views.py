from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, Count, F, Avg
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from decimal import Decimal
from datetime import timedelta
import calendar

from medicines.models import Medicine
from inventory.models import InventoryBatch
from sales.models import Sale, SaleItem


# ─────────────────────────────────────────────────────────────
#  PERMISSION MIXIN
# ─────────────────────────────────────────────────────────────

class CashierRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Restricts access to users in the Cashier group (or Superusers).
    Non-cashier authenticated users receive a 403 Forbidden.
    """
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or
            user.groups.filter(name='Cashier').exists()
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def get_cart(request):
    """Return the session cart dict."""
    return request.session.get('cart', {})



# ─────────────────────────────────────────────────────────────
#  1. CASHIER DASHBOARD
# ─────────────────────────────────────────────────────────────

class CashierDashboardView(CashierRequiredMixin, TemplateView):
    template_name = 'cashier/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        cashier = self.request.user

        # Today's stats (current cashier only)
        today_sales = Sale.objects.filter(cashier=cashier, sale_date=today)
        context['today_total_sales'] = today_sales.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
        context['today_transaction_count'] = today_sales.count()

        # Recent 10 invoices (current cashier)
        context['recent_sales'] = Sale.objects.filter(
            cashier=cashier
        ).select_related('cashier').order_by('-created_at')[:10]

        # Low stock alerts (view-only, all medicines)
        context['low_stock_items'] = InventoryBatch.objects.select_related(
            'medicine'
        ).filter(
            quantity__gt=0,
            expiry_date__gte=today
        ).order_by('quantity')[:8]

        # Expiring soon (within 30 days, view-only)
        context['expiring_soon_items'] = InventoryBatch.objects.select_related(
            'medicine'
        ).filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=30),
            quantity__gt=0
        ).order_by('expiry_date')[:8]

        # Cart item count
        cart = get_cart(self.request)
        context['cart_count'] = len(cart)

        return context


# ─────────────────────────────────────────────────────────────
#  9. CASHIER REPORTS DASHBOARD
# ─────────────────────────────────────────────────────────────

class CashierReportsDashboardView(CashierRequiredMixin, TemplateView):
    template_name = 'cashier/reports_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        cashier = self.request.user

        # Stats for this cashier
        context['today_sales_total'] = Sale.objects.filter(
            cashier=cashier, sale_date=today
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

        context['today_sales_count'] = Sale.objects.filter(
            cashier=cashier, sale_date=today
        ).count()

        context['month_sales_total'] = Sale.objects.filter(
            cashier=cashier, sale_date__gte=start_of_month
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

        context['month_sales_count'] = Sale.objects.filter(
            cashier=cashier, sale_date__gte=start_of_month
        ).count()

        context['total_all_time'] = Sale.objects.filter(
            cashier=cashier
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

        cart = get_cart(self.request)
        context['cart_count'] = len(cart)
        return context


# ─────────────────────────────────────────────────────────────
#  10. CASHIER SALES REPORT
# ─────────────────────────────────────────────────────────────

class CashierSalesReportView(CashierRequiredMixin, ListView):
    model = Sale
    template_name = 'cashier/sales_report.html'
    context_object_name = 'sales'
    paginate_by = 20

    def get_queryset(self):
        qs = Sale.objects.filter(
            cashier=self.request.user
        ).select_related('cashier').prefetch_related('items')

        # Date range
        start_date = self.request.GET.get('start_date', '').strip()
        end_date = self.request.GET.get('end_date', '').strip()
        if start_date:
            qs = qs.filter(sale_date__gte=start_date)
        if end_date:
            qs = qs.filter(sale_date__lte=end_date)

        # Payment method
        payment = self.request.GET.get('payment_method', '').strip()
        if payment:
            qs = qs.filter(payment_method=payment)

        # Invoice search
        invoice_q = self.request.GET.get('invoice_number', '').strip()
        if invoice_q:
            qs = qs.filter(invoice_number__icontains=invoice_q)

        return qs.order_by('-sale_date', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()

        agg = qs.aggregate(
            total_revenue=Sum('total_amount'),
            total_count=Count('id'),
            avg_value=Avg('total_amount'),
        )
        context['total_revenue'] = agg['total_revenue'] or Decimal('0.00')
        context['total_transactions'] = agg['total_count'] or 0
        context['avg_sale_value'] = agg['avg_value'] or Decimal('0.00')

        cart = get_cart(self.request)
        context['cart_count'] = len(cart)
        return context
