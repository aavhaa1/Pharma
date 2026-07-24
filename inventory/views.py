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
from .models import Inventory, InventoryHistory
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
        
        # 1. Search (Medicine Name, Batch Number)
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(medicine__name__icontains=q) |
                Q(batch_no__icontains=q)
            )
            
        # 2. Category Filter
        category_id = self.request.GET.get("category", "")
        if category_id:
            queryset = queryset.filter(medicine__category_id=category_id)

        # 3. Expiry / Stock Status Filter
        status_filter = self.request.GET.get("status", "").strip().lower()
        today = timezone.now().date()
        if status_filter == "expired":
            queryset = queryset.filter(expiry_date__lt=today)
        elif status_filter == "expiring_soon":
            queryset = queryset.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30))
        elif status_filter == "low_stock":
            queryset = queryset.filter(
                quantity__lte=F('medicine__minimum_stock_level'),
                quantity__gt=0,
                expiry_date__gte=today
            )
        elif status_filter == "out_of_stock":
            queryset = queryset.filter(quantity=0)
        elif status_filter == "normal":
            queryset = queryset.filter(
                expiry_date__gt=today + timedelta(days=30),
                quantity__gt=F('medicine__minimum_stock_level')
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
    Shows detail specs of a single batch, listing audit history underneath.
    """
    model = Inventory
    template_name = "inventory/inventory_detail.html"
    context_object_name = "inventory"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch audit history for this inventory batch
        context["history_logs"] = self.object.history_logs.all().select_related("user")
        return context


class InventoryAdjustView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, FormView):
    """
    Perform manual stock adjustments.
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
        inventory = self.inventory_obj
        quantity_before = inventory.quantity
        adjustment_type = form.cleaned_data.get("adjustment_type")
        quantity_changed = form.cleaned_data.get("quantity_changed")
        reason = form.cleaned_data.get("reason")

        if adjustment_type == "Increase":
            inventory.quantity += quantity_changed
            action = "Adjusted"
            changed_val = quantity_changed
        else:
            inventory.quantity -= quantity_changed
            action = "Adjusted"
            changed_val = -quantity_changed

        # Save with history log creation
        inventory.save_with_history(
            user=self.request.user,
            action=action,
            quantity_changed=changed_val,
            reason=reason,
            quantity_before=quantity_before
        )

        messages.success(self.request, "Stock adjusted successfully.")
        messages.success(self.request, "Inventory updated successfully.")
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
