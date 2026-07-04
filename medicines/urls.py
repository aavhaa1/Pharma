from django.urls import path
from . import views

urlpatterns = [
    # 📂 Categories
    path("categories/", views.CategoryListView.as_view(), name="category_list"),
    path("categories/add/", views.CategoryCreateView.as_view(), name="category_add"),
    path("categories/<int:pk>/edit/", views.CategoryUpdateView.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/", views.CategorySoftDeleteView.as_view(), name="category_delete"),

    # 💊 Medicines
    path("medicines/", views.MedicineListView.as_view(), name="medicine_list"),
    path("medicines/add/", views.MedicineCreateView.as_view(), name="medicine_add"),
    path("medicines/<int:pk>/", views.MedicineDetailView.as_view(), name="medicine_detail"),
    path("medicines/<int:pk>/edit/", views.MedicineUpdateView.as_view(), name="medicine_edit"),
    path("medicines/<int:pk>/delete/", views.MedicineSoftDeleteView.as_view(), name="medicine_delete"),
]
