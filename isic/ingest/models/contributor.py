from typing import Optional

from django.contrib.auth.models import User
from django.db import models
from django.db.models.query import QuerySet
from django.utils.safestring import mark_safe

from isic.core.models import CopyrightLicense, CreationSortedTimeStampedModel


class Contributor(CreationSortedTimeStampedModel):
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
    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_contributors')
    owners = models.ManyToManyField(User, related_name='owned_contributors')
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


class ContributorPermissions:
    model = Contributor
    perms = ['view_contributor', 'create_contributor', 'create_cohort']
    filters = {'view_contributor': 'view_contributor_list'}

    @staticmethod
    def view_contributor_list(
        user_obj: User, qs: Optional[QuerySet[Contributor]] = None
    ) -> QuerySet[Contributor]:
        qs = qs if qs is not None else Contributor._default_manager.all()

        if user_obj.is_active and user_obj.is_staff:
            return qs
        elif user_obj.is_active and user_obj.is_authenticated:
            return qs.filter(owners__in=[user_obj])
        else:
            return qs.none()

    @staticmethod
    def view_contributor(user_obj, obj):
        # TODO: use .contains in django 4
        return ContributorPermissions.view_contributor_list(user_obj).filter(pk=obj.pk).exists()

    @staticmethod
    def create_contributor(user_obj, obj=None):
        return user_obj.is_active and user_obj.is_authenticated

    @staticmethod
    def create_cohort(user_obj: User, obj: Contributor) -> bool:
        if obj:
            return user_obj.is_authenticated and ContributorPermissions.view_contributor(
                user_obj, obj
            )


Contributor.perms_class = ContributorPermissions
