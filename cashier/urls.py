from django.urls import path
from . import views

app_name = 'cashier'

urlpatterns = [
    # Dashboard
    path('', views.CashierDashboardView.as_view(), name='cashier_dashboard'),

    # Point of Sale
    path('pos/', views.CashierPOSView.as_view(), name='cashier_pos'),
    path('pos/cart/', views.CashierCartView.as_view(), name='cashier_cart'),
    path('pos/checkout/', views.CashierCheckoutView.as_view(), name='cashier_checkout'),

    # Sales History & Invoices
    path('history/', views.CashierSaleHistoryView.as_view(), name='cashier_sale_history'),
    path('history/<int:pk>/', views.CashierSaleDetailView.as_view(), name='cashier_sale_detail'),
    path('history/<int:pk>/invoice/', views.CashierInvoiceView.as_view(), name='cashier_invoice'),

    # Medicine Search (View Only)
    path('medicines/', views.CashierMedicineSearchView.as_view(), name='cashier_medicines'),

    # Reports
    path('reports/', views.CashierReportsDashboardView.as_view(), name='cashier_reports'),
    path('reports/sales/', views.CashierSalesReportView.as_view(), name='cashier_sales_report'),
]
