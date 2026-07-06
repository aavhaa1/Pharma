from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),

    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    path(
        "change-password/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/change_password.html"
        ),
        name="change_password",
    ),

    path(
        "change-password/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/change_password_done.html"
        ),
        name="password_change_done",
    ),

    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
        ),
        name="password_reset",
    ),

    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),

    path(
        "password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),

    path(
        "password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # User Management Module
    path(
        "users/",
        views.UserListView.as_view(),
        name="user_list",
    ),
    path(
        "users/add/",
        views.UserCreateView.as_view(),
        name="user_add",
    ),
    path(
        "users/<int:pk>/",
        views.UserDetailView.as_view(),
        name="user_detail",
    ),
    path(
        "users/<int:pk>/edit/",
        views.UserUpdateView.as_view(),
        name="user_edit",
    ),
    path(
        "users/<int:pk>/activate/",
        views.UserActivateView.as_view(),
        name="user_activate",
    ),
    path(
        "users/<int:pk>/deactivate/",
        views.UserDeactivateView.as_view(),
        name="user_deactivate",
    ),
]