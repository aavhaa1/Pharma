from django.urls import path
from . import views

urlpatterns = [
    path("suppliers/", views.SupplierListView.as_view(), name="supplier_list"),
    path("suppliers/add/", views.SupplierCreateView.as_view(), name="supplier_add"),
    path("suppliers/<int:pk>/", views.SupplierDetailView.as_view(), name="supplier_detail"),
    path("suppliers/<int:pk>/edit/", views.SupplierUpdateView.as_view(), name="supplier_edit"),
    path("suppliers/<int:pk>/toggle-status/", views.ToggleSupplierStatusView.as_view(), name="supplier_toggle_status"),
]
