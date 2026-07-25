from django.urls import path
from . import views

urlpatterns = [
    path("inventory/", views.InventoryListView.as_view(), name="inventory_list"),
    path("inventory/<int:pk>/", views.InventoryDetailView.as_view(), name="inventory_detail"),
    path("inventory/<int:pk>/adjust/", views.InventoryAdjustView.as_view(), name="inventory_adjust"),
    path("inventory/history/", views.InventoryHistoryListView.as_view(), name="inventory_history"),
]
