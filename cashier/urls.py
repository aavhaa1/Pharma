from django.urls import path
from . import views

app_name = 'cashier'

urlpatterns = [
    # Dashboard
    path('', views.CashierDashboardView.as_view(), name='cashier_dashboard'),

    # Reports
    path('reports/', views.CashierReportsDashboardView.as_view(), name='cashier_reports'),
    path('reports/sales/', views.CashierSalesReportView.as_view(), name='cashier_sales_report'),
]
