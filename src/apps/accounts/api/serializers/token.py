"""Response schemas for endpoints that issue JWT tokens."""

from rest_framework import serializers

from .user import UserSerializer


class TokenPairSerializer(serializers.Serializer):
    """A JWT access token and the refresh token used to renew it."""

    access = serializers.CharField()
    refresh = serializers.CharField()


class AuthResponseSerializer(serializers.Serializer):
    """Body returned by register and login: the user profile and a token pair."""

    user = UserSerializer()
    tokens = TokenPairSerializer()
