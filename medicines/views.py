from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from accounts.utils import is_admin, is_pharmacist
from .forms import CategoryForm, MedicineForm
from .models import Category, Medicine


# ─────────────────────────────────────────────────────────────────────────────
# 🛡️ PERMISSION MIXIN
# ─────────────────────────────────────────────────────────────────────────────

class AdminOrPharmacistRequiredMixin(UserPassesTestMixin):
    """
    Restricts access to Admin and Pharmacist roles only.
    Cashiers will receive a 403 Forbidden page.
    """
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (is_admin(user) or is_pharmacist(user))


# ─────────────────────────────────────────────────────────────────────────────
# 📂 CATEGORY VIEWS
# ─────────────────────────────────────────────────────────────────────────────

class CategoryListView(LoginRequiredMixin, ListView):
    """
    Lists all medicine categories.
    Accessible by: Admin, Pharmacist, Cashier (read-only).
    """
    model = Category
    template_name = "medicines/category_list.html"
    context_object_name = "categories"


class CategoryCreateView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Create a new category.
    Accessible by: Admin, Pharmacist.
    """
    model = Category
    form_class = CategoryForm
    template_name = "medicines/category_form.html"
    success_url = reverse_lazy("category_list")
    success_message = "Category '%(name)s' was created successfully."


class CategoryUpdateView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Update an existing category.
    Accessible by: Admin, Pharmacist.
    """
    model = Category
    form_class = CategoryForm
    template_name = "medicines/category_form.html"
    success_url = reverse_lazy("category_list")
    success_message = "Category '%(name)s' was updated successfully."


class CategorySoftDeleteView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, DeleteView):
    """
    Soft-deletes (deactivates) a category.
    Instead of hard deleting from the DB, sets `is_active=False`.
    Accessible by: Admin, Pharmacist.
    """
    model = Category
    template_name = "medicines/category_confirm_delete.html"
    success_url = reverse_lazy("category_list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.is_active = False
        self.object.save()
        messages.success(
            request,
            f"Category '{self.object.name}' has been successfully deactivated."
        )
        return HttpResponseRedirect(success_url)


# ─────────────────────────────────────────────────────────────────────────────
# 💊 MEDICINE VIEWS
# ─────────────────────────────────────────────────────────────────────────────

class MedicineListView(LoginRequiredMixin, ListView):
    """
    Lists all medicines with search, filtering, and pagination.
    Accessible by: Admin, Pharmacist, Cashier (read-only).
    """
    model = Medicine
    template_name = "medicines/medicine_list.html"
    context_object_name = "medicines"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # 1. Search Query (Name, Brand, Description)
        q = self.request.GET.get("q", "").strip()
        if q:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(name__icontains=q) | 
                Q(brand__icontains=q) | 
                Q(description__icontains=q)
            )

        # 2. Category Filter
        category_id = self.request.GET.get("category", "")
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # 3. Status Filter (active / inactive / all)
        status = self.request.GET.get("status", "")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)

        return queryset.select_related("category")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch active categories for the filter dropdown
        context["filter_categories"] = Category.objects.filter(is_active=True)
        
        # Preserve filter states in the UI
        context["selected_category"] = self.request.GET.get("category", "")
        context["selected_status"] = self.request.GET.get("status", "")
        context["search_query"] = self.request.GET.get("q", "")

        # URL encode parameters (excluding 'page') to preserve them in pagination links
        params = self.request.GET.copy()
        if "page" in params:
            del params["page"]
        context["query_params"] = params.urlencode()
        return context



class MedicineDetailView(LoginRequiredMixin, DetailView):
    """
    View details of a specific medicine.
    Accessible by: Admin, Pharmacist, Cashier.
    """
    model = Medicine
    template_name = "medicines/medicine_detail.html"
    context_object_name = "medicine"


class MedicineCreateView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Add a new medicine to the catalog.
    Accessible by: Admin, Pharmacist.
    """
    model = Medicine
    form_class = MedicineForm
    template_name = "medicines/medicine_form.html"
    success_url = reverse_lazy("medicine_list")
    success_message = "Medicine '%(name)s' was added successfully."


class MedicineUpdateView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Edit details of an existing medicine.
    Accessible by: Admin, Pharmacist.
    """
    model = Medicine
    form_class = MedicineForm
    template_name = "medicines/medicine_form.html"
    success_url = reverse_lazy("medicine_list")
    success_message = "Medicine '%(name)s' was updated successfully."


class MedicineSoftDeleteView(LoginRequiredMixin, AdminOrPharmacistRequiredMixin, DeleteView):
    """
    Soft-deletes (deactivates) a medicine.
    Instead of hard deleting from the DB, sets `is_active=False`.
    Accessible by: Admin, Pharmacist.
    """
    model = Medicine
    template_name = "medicines/medicine_confirm_delete.html"
    success_url = reverse_lazy("medicine_list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.is_active = False
        self.object.save()
        messages.success(
            request,
            f"Medicine '{self.object.name}' has been successfully deactivated."
        )
        return HttpResponseRedirect(success_url)
