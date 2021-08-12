from django.db import models
from django.urls import reverse

from isic.core.models.base import CreationSortedTimeStampedModel
from isic.ingest.models import Accession

from .isic_id import IsicId


class Image(CreationSortedTimeStampedModel):
    accession = models.OneToOneField(
        Accession,
        on_delete=models.PROTECT,
    )
    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(
        IsicId, on_delete=models.PROTECT, default=IsicId.safe_create, editable=False
    )

    public = models.BooleanField(default=False)

    def __str__(self):
        return self.isic_id

    def get_absolute_url(self):
        return reverse('core/image-detail', args=[self.pk])

    @property
    def as_elasticsearch_document(self) -> dict:
        m = dict(self.accession.metadata)

        # The age has to be stored in the search index in rounded form, otherwise searches
        # (e.g. 'age:47') could leak the true age.
        if 'age' in m:
            m['age_approx'] = self.accession.age_approx
            del m['age']

        for f in ['patient_id', 'lesion_id']:
            if f in m:
                del m[f]

        return {
            **{
                'id': self.pk,
                'created': self.created,
                'isic_id': self.isic_id,
                'public': self.public,
            },
            **m,
        }


class ImagePermissions:
    model = Image
    perms = ['view_image']
    filters = {'view_image': 'view_image_list'}

    @staticmethod
    def view_image_list(user_obj, qs=None):
        qs = qs if qs is not None else Image._default_manager.all()

        if user_obj.is_staff:
            return qs
        else:
            return qs.filter(public=True)

    @staticmethod
    def view_image(user_obj, obj):
        # TODO: use .contains in django 4
        return ImagePermissions.view_image_list(user_obj).filter(pk=obj.pk).exists()


Image.perms_class = ImagePermissions
