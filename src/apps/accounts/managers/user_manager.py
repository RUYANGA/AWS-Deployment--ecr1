"""Model manager for the email-based user model."""

from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """Manager for a user model that uses email as the unique identifier."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a user with a normalised email and a hashed password."""
        if not email:
            raise ValueError("The email address must be set.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user.

        Args:
            email: Email address; normalised to lowercase and used to log in.
            password: Raw password to hash. ``None`` creates a user that cannot log in
                with a password.
            **extra_fields: Additional model fields, e.g. ``first_name``.

        Returns:
            The created user.

        Raises:
            ValueError: If ``email`` is empty.
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with staff and superuser rights.

        Args:
            email: Email address; normalised to lowercase and used to log in.
            password: Raw password to hash.
            **extra_fields: Additional model fields, e.g. ``first_name``.

        Returns:
            The created superuser.

        Raises:
            ValueError: If ``email`` is empty, or ``is_staff`` / ``is_superuser`` is
                explicitly set to something other than ``True``.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)
