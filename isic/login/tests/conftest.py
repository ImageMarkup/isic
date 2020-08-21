from pytest_factoryboy import register

from .factories import GirderUserFactory

register(GirderUserFactory, 'girder_user')
