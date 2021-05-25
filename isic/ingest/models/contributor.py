from django.contrib.auth.models import User
from django.db import models
from django.utils.safestring import mark_safe

from isic.core.models import CopyrightLicense, CreationSortedTimeStampedModel


class Contributor(CreationSortedTimeStampedModel):
    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    institution_name = models.CharField(
        max_length=255,
        verbose_name='Institution Name',
        help_text=mark_safe(
            'The full name of your affiliated institution. <strong>This is private</strong>, '
            'and will not be published along with your images.'
        ),
    )
    institution_url = models.URLField(
        blank=True,
        verbose_name='Institution URL',
        help_text=mark_safe(
            'The URL of your affiliated institution. <strong>This is private</strong>, and '
            'will not be published along with your images.'
        ),
    )
    legal_contact_info = models.TextField(
        verbose_name='Legal Contact Information',
        help_text=mark_safe(
            'The person or institution responsible for legal inquiries about your data. '
            '<strong> This is private</strong>, and will not be published along with your images.'
        ),
    )
    default_copyright_license = models.CharField(
        choices=CopyrightLicense.choices,
        max_length=255,
        blank=True,
        verbose_name='Default Copyright License',
    )
    default_attribution = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Default Attribution',
        help_text=mark_safe(
            'Text which must be reproduced by users of your images, to comply with Creative '
            'Commons Attribution requirements.'
        ),
    )

    def __str__(self) -> str:
        return self.institution_name
