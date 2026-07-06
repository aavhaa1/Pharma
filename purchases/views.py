from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.db import transaction
from django.db.models import Q
from decimal import Decimal

from accounts.utils import is_admin, is_pharmacist
from medicines.views import AdminOrPharmacistRequiredMixin
from .models import Purchase, PurchaseItem
from .forms import PurchaseForm, PurchaseItemFormSet
from inventory.models import Inventory

class PurchaseListView(LoginRequiredMixin, ListView):
    model = Purchase
    template_name = 'purchases/purchase_list.html'
    context_object_name = 'purchases'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Search by supplier
        q_supplier = self.request.GET.get('supplier', '').strip()
        if q_supplier:
            queryset = queryset.filter(supplier__name__icontains=q_supplier)

        # Search by invoice number
        q_invoice = self.request.GET.get('invoice', '').strip()
        if q_invoice:
            queryset = queryset.filter(invoice_number__icontains=q_invoice)

        # Filter by status
        status = self.request.GET.get('status', '').strip()
        if status:
            queryset = queryset.filter(status=status)

        # Filter by purchase date
        purchase_date = self.request.GET.get('purchase_date', '').strip()
        if purchase_date:
            queryset = queryset.filter(purchase_date=purchase_date)

        return queryset


class PurchaseCreateView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, SuccessMessageMixin, CreateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = 'purchases/purchase_form.html'
    success_url = reverse_lazy('purchase_list')
    success_message = "Purchase created successfully."

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = PurchaseItemFormSet(self.request.POST)
        else:
            data['items'] = PurchaseItemFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        
        if items.is_valid():
            with transaction.atomic():
                form.instance.created_by = self.request.user
                form.instance.status = 'Pending'
                self.object = form.save()
                
                items.instance = self.object
                items.save()
                
                # Calculate total amount
                total = sum(item.total_cost for item in self.object.items.all())
                self.object.total_amount = total
                self.object.save()
                
            return super().form_valid(form)
        else:
            return self.form_invalid(form)


class PurchaseUpdateView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = 'purchases/purchase_form.html'
    success_url = reverse_lazy('purchase_list')
    success_message = "Purchase updated successfully."

    def dispatch(self, request, *args, **kwargs):
        purchase = self.get_object()
        if purchase.status != 'Pending':
            messages.error(request, "Only Pending purchases can be updated.")
            return redirect('purchase_detail', pk=purchase.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = PurchaseItemFormSet(self.request.POST, instance=self.object)
        else:
            data['items'] = PurchaseItemFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        
        if items.is_valid():
            with transaction.atomic():
                self.object = form.save()
                items.instance = self.object
                items.save()
                
                # Recalculate total amount
                total = sum(item.total_cost for item in self.object.items.all())
                self.object.total_amount = total
                self.object.save()
                
            return super().form_valid(form)
        else:
            return self.form_invalid(form)


class PurchaseDetailView(LoginRequiredMixin, DetailView):
    model = Purchase
    template_name = 'purchases/purchase_detail.html'
    context_object_name = 'purchase'


class ReceivePurchaseView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        purchase = get_object_or_404(Purchase, pk=pk)
        
        if purchase.status != 'Pending':
            messages.error(request, "Only Pending purchases can be received.")
            return redirect('purchase_detail', pk=purchase.pk)

        with transaction.atomic():
            purchase.status = 'Received'
            purchase.save()

            for item in purchase.items.all():
                # Get or create inventory batch based on medicine and batch number
                inventory_batch, created = Inventory.objects.get_or_create(
                    medicine=item.medicine,
                    batch_no=item.batch_no,
                    defaults={
                        'expiry_date': item.expiry_date,
                        'quantity': 0
                    }
                )
                
                # Update expiry date if it was created or if different
                if not created and inventory_batch.expiry_date != item.expiry_date:
                    inventory_batch.expiry_date = item.expiry_date

                quantity_before = inventory_batch.quantity
                inventory_batch.quantity += item.quantity
                
                inventory_batch.save_with_history(
                    user=request.user,
                    action="Added",
                    quantity_changed=item.quantity,
                    reason="New Stock",
                    quantity_before=quantity_before
                )

            messages.success(request, "Purchase received successfully.")
            
        return redirect('purchase_detail', pk=purchase.pk)


class CancelPurchaseView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        purchase = get_object_or_404(Purchase, pk=pk)
        
        if purchase.status != 'Pending':
            messages.error(request, "Only Pending purchases can be cancelled.")
            return redirect('purchase_detail', pk=purchase.pk)

        purchase.status = 'Cancelled'
        purchase.save()
        messages.success(request, "Purchase cancelled successfully.")
        
        return redirect('purchase_detail', pk=purchase.pk)
