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
from inventory.models import Inventory
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

CART_KEY = 'cashier_cart'


def get_cart(request):
    """Return the cashier session cart dict."""
    return request.session.get(CART_KEY, {})


def save_cart(request, cart):
    """Persist the cart back to the session."""
    request.session[CART_KEY] = cart


def build_cart_items(cart):
    """
    Given a cart dict {str(med_id): {quantity: N}},
    return a list of dicts with medicine objects, quantities, and totals.
    Also returns the subtotal.
    """
    cart_items = []
    subtotal = Decimal('0.00')
    today = timezone.now().date()

    for med_id_str, item in cart.items():
        try:
            medicine = Medicine.objects.select_related('category').get(pk=int(med_id_str), is_active=True)
        except Medicine.DoesNotExist:
            continue
        qty = item.get('quantity', 0)
        if qty <= 0:
            continue

        # Available unexpired stock
        available = Inventory.objects.filter(
            medicine=medicine,
            expiry_date__gte=today,
            quantity__gt=0
        ).aggregate(total=Sum('quantity'))['total'] or 0

        line_total = Decimal(str(qty)) * medicine.selling_price
        subtotal += line_total
        cart_items.append({
            'medicine': medicine,
            'quantity': qty,
            'available_stock': available,
            'unit_price': medicine.selling_price,
            'total_price': line_total,
        })

    return cart_items, subtotal


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
        context['low_stock_items'] = Inventory.objects.select_related(
            'medicine'
        ).filter(
            quantity__lte=F('medicine__minimum_stock_level'),
            quantity__gt=0
        ).order_by('quantity')[:8]

        # Expiring soon (within 30 days, view-only)
        context['expiring_soon_items'] = Inventory.objects.select_related(
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
#  2. POS – NEW SALE
# ─────────────────────────────────────────────────────────────

class CashierPOSView(CashierRequiredMixin, TemplateView):
    template_name = 'cashier/pos.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        q = self.request.GET.get('q', '').strip()

        # Medicine search
        medicines_qs = Medicine.objects.filter(is_active=True).order_by('name')
        if q:
            medicines_qs = medicines_qs.filter(
                Q(name__icontains=q) |
                Q(brand__icontains=q) |
                Q(description__icontains=q)
            )

        # Annotate with available stock
        medicines_list = []
        for med in medicines_qs[:20]:
            available = Inventory.objects.filter(
                medicine=med,
                expiry_date__gte=today,
                quantity__gt=0
            ).aggregate(total=Sum('quantity'))['total'] or 0
            nearest_expiry = Inventory.objects.filter(
                medicine=med,
                expiry_date__gte=today,
                quantity__gt=0
            ).order_by('expiry_date').values_list('expiry_date', flat=True).first()
            med.available_stock = available
            med.nearest_expiry = nearest_expiry
            medicines_list.append(med)

        context['medicines'] = medicines_list
        context['search_query'] = q

        # Cart sidebar
        cart = get_cart(self.request)
        cart_items, subtotal = build_cart_items(cart)
        context['cart_items'] = cart_items
        context['cart_subtotal'] = subtotal
        context['cart_count'] = len(cart_items)

        return context


# ─────────────────────────────────────────────────────────────
#  3. CART MANAGEMENT (POST only)
# ─────────────────────────────────────────────────────────────

class CashierCartView(CashierRequiredMixin, View):
    """Handles cart add/update/remove/clear via POST."""

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        medicine_id = request.POST.get('medicine_id', '')
        cart = get_cart(request)
        today = timezone.now().date()

        if action == 'add':
            try:
                qty = int(request.POST.get('quantity', 1))
            except (ValueError, TypeError):
                qty = 1

            if qty <= 0:
                messages.error(request, 'Quantity must be greater than zero.')
                return redirect('cashier_pos')

            try:
                medicine = Medicine.objects.get(pk=int(medicine_id), is_active=True)
            except (Medicine.DoesNotExist, ValueError):
                messages.error(request, 'Medicine not found or inactive.')
                return redirect('cashier_pos')

            # Validate unexpired stock
            available = Inventory.objects.filter(
                medicine=medicine,
                expiry_date__gte=today,
                quantity__gt=0
            ).aggregate(total=Sum('quantity'))['total'] or 0

            current_qty = cart.get(str(medicine_id), {}).get('quantity', 0)
            new_qty = current_qty + qty

            if new_qty > available:
                messages.error(
                    request,
                    f'Insufficient unexpired stock for {medicine.name}. '
                    f'Available: {available}, Requested total: {new_qty}.'
                )
                return redirect('cashier_pos')

            cart[str(medicine_id)] = {'quantity': new_qty}
            save_cart(request, cart)
            messages.success(request, f'"{medicine.name}" added to cart (qty: {new_qty}).')

        elif action == 'update':
            try:
                qty = int(request.POST.get('quantity', 0))
            except (ValueError, TypeError):
                qty = 0

            if qty <= 0:
                cart.pop(str(medicine_id), None)
                save_cart(request, cart)
                messages.success(request, 'Item removed from cart.')
            else:
                try:
                    medicine = Medicine.objects.get(pk=int(medicine_id), is_active=True)
                except (Medicine.DoesNotExist, ValueError):
                    messages.error(request, 'Medicine not found.')
                    return redirect('cashier_checkout')

                available = Inventory.objects.filter(
                    medicine=medicine,
                    expiry_date__gte=today,
                    quantity__gt=0
                ).aggregate(total=Sum('quantity'))['total'] or 0

                if qty > available:
                    messages.error(
                        request,
                        f'Cannot set quantity to {qty}. Max available (unexpired): {available}.'
                    )
                    return redirect('cashier_checkout')

                cart[str(medicine_id)] = {'quantity': qty}
                save_cart(request, cart)
                messages.success(request, 'Cart quantity updated.')

        elif action == 'remove':
            cart.pop(str(medicine_id), None)
            save_cart(request, cart)
            messages.success(request, 'Item removed from cart.')

        elif action == 'clear':
            save_cart(request, {})
            messages.success(request, 'Cart cleared.')

        # Redirect back to the referring page (POS or checkout)
        referer = request.POST.get('next', 'cashier_pos')
        if referer == 'checkout':
            return redirect('cashier_checkout')
        return redirect('cashier_pos')


# ─────────────────────────────────────────────────────────────
#  4. CHECKOUT
# ─────────────────────────────────────────────────────────────

class CashierCheckoutView(CashierRequiredMixin, View):
    template_name = 'cashier/checkout.html'

    def get(self, request, *args, **kwargs):
        cart = get_cart(request)
        if not cart:
            messages.warning(request, 'Your cart is empty. Please add items first.')
            return redirect('cashier_pos')

        cart_items, subtotal = build_cart_items(cart)
        return render(request, self.template_name, {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'cart_count': len(cart_items),
        })

    def post(self, request, *args, **kwargs):
        cart = get_cart(request)
        if not cart:
            messages.error(request, 'Your cart is empty.')
            return redirect('cashier_pos')

        customer_name = request.POST.get('customer_name', '').strip()
        payment_method = request.POST.get('payment_method', 'Cash')

        try:
            discount = Decimal(request.POST.get('discount', '0') or '0')
            tax = Decimal(request.POST.get('tax', '0') or '0')
        except Exception:
            discount = Decimal('0.00')
            tax = Decimal('0.00')

        today = timezone.now().date()

        try:
            with transaction.atomic():
                subtotal = Decimal('0.00')
                sale_items_data = []

                for med_id_str, item in cart.items():
                    medicine = get_object_or_404(Medicine, pk=int(med_id_str))
                    if not medicine.is_active:
                        raise ValueError(f'"{medicine.name}" is no longer active and cannot be sold.')

                    qty_requested = item.get('quantity', 0)
                    if qty_requested <= 0:
                        continue

                    # FIFO: unexpired batches ordered by expiry date
                    batches = Inventory.objects.filter(
                        medicine=medicine,
                        expiry_date__gte=today,
                        quantity__gt=0
                    ).order_by('expiry_date')

                    total_available = batches.aggregate(total=Sum('quantity'))['total'] or 0

                    if qty_requested > total_available:
                        raise ValueError(
                            f'Not enough unexpired stock for "{medicine.name}". '
                            f'Requested: {qty_requested}, Available: {total_available}.'
                        )

                    subtotal += Decimal(str(qty_requested)) * medicine.selling_price
                    sale_items_data.append((medicine, qty_requested, batches))

                if not sale_items_data:
                    raise ValueError('No valid items in cart to process.')

                # Create Sale record
                invoice_number = Sale.generate_next_invoice_number()
                total_amount = subtotal - discount + tax
                if total_amount < Decimal('0.00'):
                    total_amount = Decimal('0.00')

                sale = Sale.objects.create(
                    invoice_number=invoice_number,
                    customer_name=customer_name or None,
                    payment_method=payment_method,
                    subtotal=subtotal,
                    discount=discount,
                    tax=tax,
                    total_amount=total_amount,
                    cashier=request.user,
                )

                # Deduct stock FIFO and create SaleItems
                for medicine, qty_requested, batches in sale_items_data:
                    remaining = qty_requested
                    for batch in batches:
                        if remaining <= 0:
                            break
                        deduct = min(remaining, batch.quantity)

                        SaleItem.objects.create(
                            sale=sale,
                            medicine=medicine,
                            inventory_batch=batch,
                            quantity=deduct,
                            unit_price=medicine.selling_price,
                            total_price=Decimal(str(deduct)) * medicine.selling_price,
                        )

                        qty_before = batch.quantity
                        batch.quantity -= deduct
                        batch.save_with_history(
                            user=request.user,
                            action='Removed',
                            quantity_changed=-deduct,
                            reason='Sale',
                            quantity_before=qty_before,
                        )
                        remaining -= deduct

                # Clear cart
                save_cart(request, {})

                messages.success(request, f'Sale completed! Invoice {invoice_number} generated.')
                return redirect('cashier_sale_detail', pk=sale.pk)

        except ValueError as e:
            messages.error(request, f'Checkout failed: {e}')
            return redirect('cashier_checkout')
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {e}')
            return redirect('cashier_checkout')


# ─────────────────────────────────────────────────────────────
#  5. SALES HISTORY
# ─────────────────────────────────────────────────────────────

class CashierSaleHistoryView(CashierRequiredMixin, ListView):
    model = Sale
    template_name = 'cashier/sale_history.html'
    context_object_name = 'sales'
    paginate_by = 15

    def get_queryset(self):
        # Cashiers see only their own sales
        qs = Sale.objects.filter(
            cashier=self.request.user
        ).select_related('cashier').prefetch_related('items')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(invoice_number__icontains=q) |
                Q(customer_name__icontains=q)
            )

        date_filter = self.request.GET.get('date', '').strip()
        if date_filter:
            qs = qs.filter(sale_date=date_filter)

        payment = self.request.GET.get('payment_method', '').strip()
        if payment:
            qs = qs.filter(payment_method=payment)

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = get_cart(self.request)
        context['cart_count'] = len(cart)
        return context


# ─────────────────────────────────────────────────────────────
#  6. SALE DETAIL (VIEW ONLY)
# ─────────────────────────────────────────────────────────────

class CashierSaleDetailView(CashierRequiredMixin, DetailView):
    model = Sale
    template_name = 'cashier/sale_detail.html'
    context_object_name = 'sale'

    def get_object(self, queryset=None):
        sale = get_object_or_404(
            Sale.objects.select_related('cashier').prefetch_related('items__medicine', 'items__inventory_batch'),
            pk=self.kwargs['pk']
        )
        # Cashiers may only view their own sales (superusers bypass)
        if not self.request.user.is_superuser and sale.cashier != self.request.user:
            raise PermissionDenied
        return sale

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = get_cart(self.request)
        context['cart_count'] = len(cart)
        return context


# ─────────────────────────────────────────────────────────────
#  7. PRINTABLE INVOICE
# ─────────────────────────────────────────────────────────────

class CashierInvoiceView(CashierRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        sale = get_object_or_404(
            Sale.objects.select_related('cashier').prefetch_related('items__medicine', 'items__inventory_batch'),
            pk=pk
        )
        if not request.user.is_superuser and sale.cashier != request.user:
            raise PermissionDenied

        return render(request, 'cashier/invoice.html', {'sale': sale})


# ─────────────────────────────────────────────────────────────
#  8. MEDICINE SEARCH (VIEW ONLY)
# ─────────────────────────────────────────────────────────────

class CashierMedicineSearchView(CashierRequiredMixin, TemplateView):
    template_name = 'cashier/medicine_search.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        q = self.request.GET.get('q', '').strip()

        medicines_qs = Medicine.objects.filter(is_active=True).select_related('category').order_by('name')
        if q:
            medicines_qs = medicines_qs.filter(
                Q(name__icontains=q) |
                Q(brand__icontains=q) |
                Q(description__icontains=q)
            )

        medicines_list = []
        for med in medicines_qs[:50]:
            batches = Inventory.objects.filter(
                medicine=med,
                expiry_date__gte=today,
                quantity__gt=0
            ).order_by('expiry_date')
            available = batches.aggregate(total=Sum('quantity'))['total'] or 0
            nearest_expiry = batches.values_list('expiry_date', flat=True).first()
            med.available_stock = available
            med.nearest_expiry = nearest_expiry
            medicines_list.append(med)

        context['medicines'] = medicines_list
        context['search_query'] = q
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
