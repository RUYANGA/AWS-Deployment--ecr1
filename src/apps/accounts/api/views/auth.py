"""Authentication endpoints: register, email verification, login, refresh and logout."""

from django.contrib.auth.models import update_last_login
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from ...models import User
from ...utils import issue_email_otp, seconds_until_resend, tokens_for_user
from ..serializers import (
    AuthResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    MessageSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from ..throttles import AuthRateThrottle

TAG = "Authentication"

SEND_FAILED = "We could not send the verification email. Request a new code."


class RegisterView(generics.GenericAPIView):
    """Create an account and email a verification code to it."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=[TAG],
        summary="Register a new user",
        responses={
            201: RegisterResponseSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
    )
    def post(self, request):
        """Register a user with email and password and email them a verification code.

        The email must be unique (case-insensitive) and the password must pass the
        password validators. No tokens are issued: confirm the email with
        ``verify-email`` to sign in. Rate-limited per IP address.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        sent = issue_email_otp(user)
        detail = f"A verification code was sent to {user.email}." if sent else SEND_FAILED
        return Response(
            {"detail": detail, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(generics.GenericAPIView):
    """Confirm an email address with its one-time code and sign the user in."""

    serializer_class = VerifyEmailSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=[TAG],
        summary="Verify the email address with the emailed code",
        responses={
            200: AuthResponseSerializer,
            400: OpenApiResponse(
                description="Unknown or already verified account, or a missing, expired, "
                "locked or wrong code"
            ),
        },
    )
    def post(self, request):
        """Verify the email address and return the profile with JWT tokens.

        The code is valid for a limited time and can be tried a limited number of times.
        When it has expired or is locked, request a new one with
        ``resend-verification``. Rate-limited per IP address.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        update_last_login(None, user)
        return Response({"user": UserSerializer(user).data, "tokens": tokens_for_user(user)})


class ResendVerificationView(generics.GenericAPIView):
    """Email a new verification code, replacing the previous one."""

    serializer_class = ResendVerificationSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=[TAG],
        summary="Resend the email verification code",
        responses={
            200: MessageSerializer,
            429: OpenApiResponse(description="A code was sent too recently; retry later"),
            503: OpenApiResponse(description="The email could not be sent"),
        },
    )
    def post(self, request):
        """Send a new verification code to an unverified account.

        Use this when the previous code expired, was locked after too many wrong
        attempts, or never arrived. The previous code stops working. A new code can be
        requested once per cooldown period; the ``Retry-After`` header gives the wait in
        seconds. The response is the same whether or not the account exists. Rate-limited
        per IP address.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"],
            is_active=True,
            is_email_verified=False,
        ).first()
        if user is not None:
            wait = seconds_until_resend(user)
            if wait:
                return Response(
                    {"detail": f"Wait {wait} seconds before requesting a new code."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={"Retry-After": str(wait)},
                )
            if not issue_email_otp(user):
                return Response({"detail": SEND_FAILED}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            {"detail": "If the account exists and is not verified, a new code was sent."}
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
            403: OpenApiResponse(description="Email address not verified yet"),
        },
    )
    def post(self, request):
        """Authenticate with email and password and return the profile with JWT tokens.

        The email address must be verified first; otherwise the response is 403 with
        ``code`` set to ``email_not_verified``. Updates the user's last login time.
        Rate-limited per IP address.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        if not user.is_email_verified:
            return Response(
                {"detail": "Verify your email address first.", "code": "email_not_verified"},
                status=status.HTTP_403_FORBIDDEN,
            )
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
