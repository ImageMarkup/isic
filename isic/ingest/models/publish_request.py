from django.contrib.auth.models import User
from django.db import models


class PublishRequestAccession(models.Model):
    publish_request = models.ForeignKey("PublishRequest", on_delete=models.PROTECT)
    accession = models.OneToOneField("Accession", on_delete=models.PROTECT)

    def __str__(self) -> str:
        return f"PublishRequestAccession {self.pk}"


class PublishRequest(models.Model):
    """
    Stores a record of a user's request to publish a set of accessions.

    This is necessary because the publish process can be multiple stages, including
    unembargoing, and there needs to be a reference to the specific accessions to be
    published.
    """

    created = models.DateTimeField(auto_now_add=True)
    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    accessions = models.ManyToManyField("Accession", through="PublishRequestAccession")
    # the additional collections to which the images will be added, including the magic collection
    collections = models.ManyToManyField("core.Collection")
    public = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"PublishRequest {self.pk}"
