from django.urls import path
from . import views

urlpatterns = [
    path('', views.ReportsDashboardView.as_view(), name='reports_home'),
    path('dashboard/', views.ReportsDashboardView.as_view(), name='reports_dashboard'),
    path('sales/', views.SalesReportView.as_view(), name='reports_sales'),
    path('purchases/', views.PurchaseReportView.as_view(), name='reports_purchases'),
    path('inventory/', views.InventoryReportView.as_view(), name='reports_inventory'),
    path('medicines/', views.MedicineReportView.as_view(), name='reports_medicines'),
    path('suppliers/', views.SupplierReportView.as_view(), name='reports_suppliers'),
    path('low-stock/', views.LowStockReportView.as_view(), name='reports_low_stock'),
    path('expiry/', views.ExpiryReportView.as_view(), name='reports_expiry'),
    path('revenue/', views.RevenueReportView.as_view(), name='reports_revenue'),
    path('export/pdf/', views.ExportPDFView.as_view(), name='reports_export_pdf'),
    path('export/excel/', views.ExportExcelView.as_view(), name='reports_export_excel'),
    path('export/csv/', views.ExportCSVView.as_view(), name='reports_export_csv'),
]
