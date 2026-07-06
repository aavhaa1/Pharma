from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.models import User
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from accounts.utils import is_admin
from .forms import UserCreateForm, UserEditForm

# 🛡️ PERMISSION MIXIN
class AdminRequiredMixin(UserPassesTestMixin):
    """
    Restricts access to Admin role (users in the Admin group) or Superusers.
    Pharmacists and Cashiers will receive a 403 Forbidden page.
    """
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or is_admin(user))

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().handle_no_permission()


# 👥 USER VIEWS
class UserListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """
    Lists all users with search, role filtering, status filtering, and pagination.
    """
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users_list"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()

        # 1. Search Query (Username, Email, Full Name)
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.annotate(
                full_name=Concat("first_name", Value(" "), "last_name")
            ).filter(
                Q(username__icontains=q) |
                Q(email__icontains=q) |
                Q(full_name__icontains=q)
            )

        # 2. Role Filter
        role = self.request.GET.get("role", "")
        if role:
            queryset = queryset.filter(groups__name=role)

        # 3. Status Filter (active / inactive)
        status = self.request.GET.get("status", "")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)

        return queryset.prefetch_related("groups").order_by("-date_joined")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Filters state preservation
        context["selected_role"] = self.request.GET.get("role", "")
        context["selected_status"] = self.request.GET.get("status", "")
        context["search_query"] = self.request.GET.get("q", "")

        # Preserve query parameters in pagination
        params = self.request.GET.copy()
        if "page" in params:
            del params["page"]
        context["query_params"] = params.urlencode()
        return context


class UserCreateView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Form view to create a new staff account.
    """
    model = User
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("user_list")
    success_message = "User '%(username)s' was created successfully."


class UserUpdateView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Form view to update details of an existing staff account.
    """
    model = User
    form_class = UserEditForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("user_list")
    success_message = "User '%(username)s' was updated successfully."


class UserDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    """
    Displays the detailed information of a specific user.
    """
    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "profile_user"


class UserActivateView(LoginRequiredMixin, AdminRequiredMixin, View):
    """
    Confirms and activates a user's account.
    """
    def get(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        return render(request, "accounts/user_confirm_status.html", {
            "target_user": target_user,
            "action": "activate"
        })

    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        target_user.is_active = True
        target_user.save()
        messages.success(request, f"User '{target_user.username}' has been successfully activated.")
        return redirect("user_list")


class UserDeactivateView(LoginRequiredMixin, AdminRequiredMixin, View):
    """
    Confirms and deactivates a user's account.
    """
    def get(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        return render(request, "accounts/user_confirm_status.html", {
            "target_user": target_user,
            "action": "deactivate"
        })

    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        target_user.is_active = False
        target_user.save()
        messages.success(request, f"User '{target_user.username}' has been successfully deactivated.")
        return redirect("user_list")
