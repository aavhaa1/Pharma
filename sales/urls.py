from django.urls import path
from . import views

urlpatterns = [
    path('', views.SaleListView.as_view(), name='sale_list'),
    path('new/', views.SaleCreateView.as_view(), name='sale_new'),
    path('cart/', views.CartView.as_view(), name='cart_view'),
    path('checkout/', views.CheckoutView.as_view(), name='checkout_view'),
    path('<int:pk>/', views.SaleDetailView.as_view(), name='sale_detail'),
    path('<int:pk>/invoice/', views.InvoiceView.as_view(), name='invoice_view'),
]
