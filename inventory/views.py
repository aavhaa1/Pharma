from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, FormView
from django.db.models import Q, F
from django.utils import timezone
from datetime import timedelta

from accounts.utils import is_admin, is_pharmacist
from medicines.models import Category, Medicine
from .models import Inventory, InventoryBatch, InventoryHistory
from .forms import InventoryForm, StockAdjustmentForm


class AdminOrPharmacistRequiredMixin(UserPassesTestMixin):
    """
    Restricts access to Admin and Pharmacist roles only.
    Cashiers will receive a 403 Forbidden page.
    """
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or is_admin(user) or is_pharmacist(user))


class InventoryListView(LoginRequiredMixin, ListView):
    """
    Lists all inventory batches in a Bootstrap table.
    Includes search and filtering functionality.
    """
    model = Inventory
    template_name = "inventory/inventory_list.html"
    context_object_name = "inventory_list"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # 1. Search (Medicine Name)
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(medicine__name__icontains=q)
            )
            
        # 2. Category Filter
        category_id = self.request.GET.get("category", "")
        if category_id:
            queryset = queryset.filter(medicine__category_id=category_id)

        # 3. Expiry / Stock Status Filter
        status_filter = self.request.GET.get("status", "").strip().lower()
        today = timezone.now().date()
        if status_filter == "expired":
            queryset = queryset.filter(medicine__inventory_batches__expiry_date__lt=today).distinct()
        elif status_filter == "expiring_soon":
            queryset = queryset.filter(
                medicine__inventory_batches__expiry_date__gte=today, 
                medicine__inventory_batches__expiry_date__lte=today + timedelta(days=30)
            ).distinct()
        elif status_filter == "low_stock":
            queryset = queryset.filter(
                current_stock__gt=0,
                current_stock__lte=F('medicine__minimum_stock_level')
            )
        elif status_filter == "out_of_stock":
            queryset = queryset.filter(current_stock=0)
        elif status_filter == "normal":
            queryset = queryset.filter(
                current_stock__gt=F('medicine__minimum_stock_level')
            )

        return queryset.select_related("medicine", "medicine__category")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Category list for filtering
        context["categories"] = Category.objects.filter(is_active=True)
        
        # Preserve filters in templates
        context["selected_category"] = self.request.GET.get("category", "")
        context["selected_status"] = self.request.GET.get("status", "")
        context["search_query"] = self.request.GET.get("q", "")

        # Preserve query string for pagination links
        params = self.request.GET.copy()
        if "page" in params:
            del params["page"]
        context["query_params"] = params.urlencode()
        return context


class InventoryCreateView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Creates a new inventory batch and logs the transaction.
    """
    model = Inventory
    form_class = InventoryForm
    template_name = "inventory/inventory_form.html"
    success_url = reverse_lazy("inventory_list")
    success_message = "Stock added successfully."

    def form_valid(self, form):
        self.object = form.save(commit=False)
        # Save inventory and automatically log history record
        self.object.save_with_history(
            user=self.request.user,
            action="Added",
            quantity_changed=self.object.quantity,
            reason="New Stock",
            quantity_before=0
        )
        messages.success(self.request, self.success_message)
        messages.success(self.request, "Inventory history recorded successfully.")
        return HttpResponseRedirect(self.get_success_url())


class InventoryDetailView(LoginRequiredMixin, DetailView):
    """
    Shows aggregate stock for a single medicine, listing all its batches and audit history.
    """
    model = Inventory
    template_name = "inventory/inventory_detail.html"
    context_object_name = "inventory"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # All batches for this medicine
        context["batches"] = self.object.medicine.inventory_batches.all().order_by("expiry_date")
        # Fetch combined audit history across all batches for this medicine
        context["history_logs"] = InventoryHistory.objects.filter(
            inventory__medicine=self.object.medicine
        ).select_related("user", "inventory").order_by("-created_at")[:50]
        return context


class InventoryAdjustView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, FormView):
    """
    Perform manual stock adjustments on a specific batch belonging to a medicine's inventory.
    """
    form_class = StockAdjustmentForm
    template_name = "inventory/inventory_adjust.html"
    success_url = reverse_lazy("inventory_list")

    def dispatch(self, request, *args, **kwargs):
        self.inventory_obj = Inventory.objects.get(pk=self.kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["inventory"] = self.inventory_obj
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["inventory"] = self.inventory_obj
        return context

    def form_valid(self, form):
        batch = form.cleaned_data.get("inventory")  # This is an InventoryBatch instance
        quantity_before = batch.quantity
        adjustment_type = form.cleaned_data.get("adjustment_type")
        quantity_changed = form.cleaned_data.get("quantity_changed")
        reason = form.cleaned_data.get("reason")

        if adjustment_type == "Increase":
            batch.quantity += quantity_changed
            changed_val = quantity_changed
        else:
            batch.quantity -= quantity_changed
            changed_val = -quantity_changed

        # Save batch with history log
        batch.save_with_history(
            user=self.request.user,
            action="Adjusted",
            quantity_changed=changed_val,
            reason=reason,
            quantity_before=quantity_before
        )

        # Update the aggregate inventory record
        self.inventory_obj.update_stock()

        messages.success(self.request, f"Stock adjusted successfully for batch {batch.batch_no}.")
        messages.success(self.request, "Inventory history recorded successfully.")
        return HttpResponseRedirect(self.get_success_url())


class InventoryHistoryListView(LoginRequiredMixin, ListView):
    """
    Lists global audit history records, newest first.
    Includes searching capability by medicine name.
    """
    model = InventoryHistory
    template_name = "inventory/inventory_history.html"
    context_object_name = "history_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(inventory__medicine__name__icontains=q)
        return queryset.select_related("inventory", "inventory__medicine", "user")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "")
        # Preserve query string for pagination links
        params = self.request.GET.copy()
        if "page" in params:
            del params["page"]
        context["query_params"] = params.urlencode()
        return context
