from allauth.account.models import EmailAddress
from bson import ObjectId
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db.models.signals import post_save
import factory
import factory.django

from isic.login.models import Profile, get_hashid


@factory.django.mute_signals(post_save)
class ProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Profile

    girder_id = factory.LazyFunction(ObjectId)
    hash_id = factory.LazyAttribute(lambda o: get_hashid(o.user.pk))
    accepted_terms = None

    # Pass in profile=None to prevent UserFactory from creating another profile this disables the
    # RelatedFactory).
    user = factory.SubFactory(
        "isic.factories.UserFactory",
        profile=None,
        raw_password=factory.SelfAttribute("..raw_password"),
    )

    class Params:
        raw_password = factory.Faker("password")


@factory.django.mute_signals(post_save)
class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.SelfAttribute("email")
    email = factory.Faker("safe_email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.LazyAttribute(lambda o: make_password(o.raw_password))

    # We pass in 'user' to link the generated Profile to our just-generated User. This will call
    # ProfileFactory(user=our_new_user), thus skipping the SubFactory.
    profile = factory.RelatedFactory(
        ProfileFactory,
        factory_related_name="user",
        raw_password=factory.SelfAttribute("..raw_password"),
    )

    class Params:
        raw_password = factory.Faker("password")

    @factory.post_generation
    def email_address(self, create, extracted, **kwargs):
        if create:
            EmailAddress.objects.create(user=self, email=self.email, verified=True, primary=True)
