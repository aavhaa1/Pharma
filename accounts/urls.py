from django.urls import path
from django.contrib.auth import views as auth_views

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
]