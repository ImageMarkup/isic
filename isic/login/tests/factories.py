from bson import ObjectId
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db.models.signals import post_save
import factory.django
from passlib.hash import bcrypt

from isic.login.models import Profile


@factory.django.mute_signals(post_save)
class ProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Profile

    girder_id = factory.LazyFunction(ObjectId)
    girder_salt = factory.LazyAttribute(
        lambda o: bcrypt.using(rounds=4).hash(o.raw_password) if o.raw_password else None
    )

    # We pass in profile=None to prevent UserFactory from creating another profile
    # (this disables the RelatedFactory)
    user = factory.SubFactory(
        'isic.login.tests.factories.UserFactory',
        profile=None,
        raw_password=factory.SelfAttribute('..raw_password'),
    )

    class Params:
        raw_password = factory.Faker('password')


@factory.django.mute_signals(post_save)
class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Faker('user_name')
    email = factory.Faker('safe_email')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    password = factory.LazyAttribute(lambda o: make_password(o.raw_password))

    # We pass in 'user' to link the generated Profile to our just-generated User
    # This will call ProfileFactory(user=our_new_user), thus skipping the SubFactory.
    profile = factory.RelatedFactory(
        ProfileFactory,
        factory_related_name='user',
        raw_password=factory.SelfAttribute('..raw_password'),
    )

    class Params:
        raw_password = factory.Faker('password')
