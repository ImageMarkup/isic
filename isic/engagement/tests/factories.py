import factory
import factory.django

from isic.engagement.models import EmailDomainContributor, EngagementProfile
from isic.factories import UserFactory
from isic.ingest.tests.factories import CohortFactory, ContributorFactory


class EngagementProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EngagementProfile

    user = factory.SubFactory(UserFactory)
    default_contributor = None
    default_cohort = None

    class Params:
        # A profile that has been through the provenance form, with a contributor/cohort
        # pair that is internally consistent.
        provisioned = factory.Trait(
            default_cohort=factory.SubFactory(CohortFactory),
            default_contributor=factory.SelfAttribute("default_cohort.contributor"),
        )


class EmailDomainContributorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailDomainContributor

    domain = factory.Sequence(lambda n: f"institution{n}.org")
    contributor = factory.SubFactory(ContributorFactory)
