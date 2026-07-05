from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    UpdateView,
)

from accounts.utils import is_admin, is_pharmacist
from .forms import SupplierForm
from .models import Supplier


# ─────────────────────────────────────────────────────────────────────────────
# 🛡️ PERMISSION MIXIN
# ─────────────────────────────────────────────────────────────────────────────

class SupplierPermissionMixin(UserPassesTestMixin):
    """
    Restricts access to Admin and Pharmacist roles only.
    Cashiers will receive a 403 Forbidden page.
    """
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or is_admin(user) or is_pharmacist(user))


# ─────────────────────────────────────────────────────────────────────────────
# 🤝 SUPPLIER VIEWS
# ─────────────────────────────────────────────────────────────────────────────

class SupplierListView(LoginRequiredMixin, SupplierPermissionMixin, ListView):
    """
    Lists all suppliers with search and active/inactive status filter.
    Default status display is active suppliers only.
    """
    model = Supplier
    template_name = "suppliers/supplier_list.html"
    context_object_name = "suppliers"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()

        # 1. Search Query (Name, Contact Person, Phone)
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(contact_person__icontains=q) |
                Q(phone__icontains=q)
            )

        # 2. Status Filter (active / inactive / all)
        status = self.request.GET.get("status", "active").strip()
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)
        # If status is "all", we don't apply any is_active filter

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Preserve search queries and filter selections in the templates
        context["search_query"] = self.request.GET.get("q", "")
        context["selected_status"] = self.request.GET.get("status", "active")

        # Encode URL parameters (excluding page) for pagination links
        params = self.request.GET.copy()
        if "page" in params:
            del params["page"]
        context["query_params"] = params.urlencode()
        
        return context


class SupplierCreateView(LoginRequiredMixin, SupplierPermissionMixin, SuccessMessageMixin, CreateView):
    """
    View for adding new suppliers.
    """
    model = Supplier
    form_class = SupplierForm
    template_name = "suppliers/supplier_form.html"
    success_url = reverse_lazy("supplier_list")
    success_message = "Supplier '%(name)s' was added successfully."


class SupplierDetailView(LoginRequiredMixin, SupplierPermissionMixin, DetailView):
    """
    View to display supplier detailed information.
    """
    model = Supplier
    template_name = "suppliers/supplier_detail.html"
    context_object_name = "supplier"


class SupplierUpdateView(LoginRequiredMixin, SupplierPermissionMixin, SuccessMessageMixin, UpdateView):
    """
    View for updating existing suppliers.
    """
    model = Supplier
    form_class = SupplierForm
    template_name = "suppliers/supplier_form.html"
    success_url = reverse_lazy("supplier_list")
    success_message = "Supplier '%(name)s' was updated successfully."


class ToggleSupplierStatusView(LoginRequiredMixin, SupplierPermissionMixin, View):
    """
    Soft-deletes (deactivates) or reactivates a supplier.
    """
    def get(self, request, pk, *args, **kwargs):
        supplier = get_object_or_404(Supplier, pk=pk)
        supplier.is_active = not supplier.is_active
        supplier.save()

        if supplier.is_active:
            messages.success(request, f"Supplier '{supplier.name}' was activated successfully.")
        else:
            messages.success(request, f"Supplier '{supplier.name}' was deactivated successfully.")

        return redirect("supplier_list")

    def post(self, request, pk, *args, **kwargs):
        return self.get(request, pk, *args, **kwargs)
