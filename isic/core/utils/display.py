from django.contrib.auth.models import User


def user_nicename(user: User) -> str:
    return f'{user.first_name} {user.last_name}'
