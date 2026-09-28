from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveBackend(ModelBackend):
    """Emails are the login name, so match them regardless of letter case."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None or password is None:
            return None
        try:
            user = User.objects.get(username__iexact=username.strip())
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            User().set_password(password)  # keep timing similar to a real check
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
