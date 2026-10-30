"""URL routes for the accounts API, mounted at ``/api/v1/``.

``auth/`` holds authentication and the user's own profile; ``users/`` is the
administrator user-management API.
"""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

app_name = "accounts"

router = SimpleRouter()
router.register("users", views.UserViewSet, basename="user")

auth_urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("token/refresh/", views.RefreshView.as_view(), name="token-refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change-password"),
]

urlpatterns = [
    path("auth/", include(auth_urlpatterns)),
    *router.urls,
]
