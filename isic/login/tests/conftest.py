from pytest_factoryboy import register

from .factories import ProfileFactory, UserFactory


# Can't use the register decorators with circular factory references
register(ProfileFactory)
register(UserFactory)
