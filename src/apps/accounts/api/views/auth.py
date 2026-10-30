"""Authentication endpoints: register, login, token refresh and logout."""

from django.contrib.auth.models import update_last_login
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from ...utils import tokens_for_user
from ..serializers import (
    AuthResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    UserSerializer,
)
from ..throttles import AuthRateThrottle

TAG = "Authentication"


class RegisterView(generics.GenericAPIView):
    """Create an account and sign the new user in."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=[TAG],
        summary="Register a new user",
        responses={
            201: AuthResponseSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
    )
    def post(self, request):
        """Register a user with email and password and return the profile with JWT tokens.

        The email must be unique (case-insensitive) and the password must pass the
        password validators. Rate-limited per IP address.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"user": UserSerializer(user).data, "tokens": tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(generics.GenericAPIView):
    """Exchange email and password for JWT tokens."""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=[TAG],
        summary="Log in with email and password",
        responses={
            200: AuthResponseSerializer,
            400: OpenApiResponse(description="Invalid credentials"),
        },
    )
    def post(self, request):
        """Authenticate with email and password and return the profile with JWT tokens.

        Updates the user's last login time. Rate-limited per IP address.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        update_last_login(None, user)
        return Response({"user": UserSerializer(user).data, "tokens": tokens_for_user(user)})


@extend_schema(tags=[TAG], summary="Refresh the access token")
class RefreshView(TokenRefreshView):
    """Exchange a refresh token for a new access token.

    Refresh tokens rotate: the response also contains a new refresh token and the old
    one is blacklisted.
    """


class LogoutView(APIView):
    """Revoke a refresh token."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[TAG],
        summary="Log out (blacklist the refresh token)",
        request=LogoutSerializer,
        responses={205: None, 400: OpenApiResponse(description="Invalid or expired token")},
    )
    def post(self, request):
        """Blacklist the given refresh token so it can no longer issue access tokens.

        Access tokens already issued stay valid until they expire.
        """
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)
