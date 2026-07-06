from django.urls import path
from . import views

urlpatterns = [
    path('', views.PurchaseListView.as_view(), name='purchase_list'),
    path('add/', views.PurchaseCreateView.as_view(), name='purchase_add'),
    path('<int:pk>/', views.PurchaseDetailView.as_view(), name='purchase_detail'),
    path('<int:pk>/edit/', views.PurchaseUpdateView.as_view(), name='purchase_edit'),
    path('<int:pk>/receive/', views.ReceivePurchaseView.as_view(), name='purchase_receive'),
    path('<int:pk>/cancel/', views.CancelPurchaseView.as_view(), name='purchase_cancel'),
]
