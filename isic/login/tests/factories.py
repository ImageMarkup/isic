from bson import ObjectId
import factory
from passlib.hash import bcrypt


class GirderUserFactory(factory.DictFactory):
    name = 'foo'
    _id = factory.LazyFunction(ObjectId)
    login = factory.Faker('user_name')
    email = factory.Faker('safe_email')
    firstName = factory.Faker('first_name')  # noqa: N815
    lastName = factory.Faker('last_name')  # noqa: N815
    status = 'enabled'
    emailVerified = True  # noqa: N815
    admin = False
    salt = factory.LazyAttribute(
        lambda o: bcrypt.using(rounds=4).hash(o.raw_password) if o.raw_password else None
    )
    created = factory.Faker('date_time_this_decade')

    class Params:
        raw_password = factory.Faker('password')
