from django.contrib.auth.models import Group, User
from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm
from guardian.utils import get_anonymous_user

from isic.core.models.image import Image, ImageShare
from isic.ingest.models import Contributor


def initialize_groups():
    staff_group, _ = Group.objects.get_or_create(name="Staff")
    staff_group.user_set.add(*User.objects.filter(is_staff=True))
    anon_user = get_anonymous_user()
    public_group, _ = Group.objects.get_or_create(name="Public")
    public_group.user_set.add(*User.objects.all(), anon_user)
    for contributor in Contributor.objects.all():
        contributor_group, _ = Group.objects.get_or_create(name=f"contributor_{contributor.id}")
        contributor_group.user_set.add(*contributor.owners.all())


def assign_image_perms():
    initialize_groups()
    all_images = Image.objects.all()
    public_images = Image.objects.filter(public=True)
    staff_group = Group.objects.get(name="Staff")
    public_group = Group.objects.get(name="Public")
    assign_perm("view_image", public_group, public_images)
    assign_perm("view_image", staff_group, all_images)
    assign_perm("view_image_metadata", staff_group, all_images)
    for image_share in ImageShare.objects.all():
        assign_perm("view_image", image_share.grantee, image_share.image)
    for contributor in Contributor.objects.all():
        contributor_group = Group.objects.get(name=f"contributor_{contributor.id}")
        contributor_images = Image.objects.filter(accession__cohort__contributor=contributor.id)
        assign_perm("view_image", contributor_group, contributor_images)
        assign_perm("view_image_metadata", contributor_group, contributor_images)


@receiver(post_save, sender=User)
def user_save_assign_groups(sender, instance, created, **kwargs):
    initialize_groups()


@receiver(post_save, sender=Image)
def image_save_assign_perms(sender, instance, created, **kwargs):
    if created:
        initialize_groups()
        staff_group = Group.objects.get(name="Staff")
        assign_perm("view_image", staff_group, instance)
        assign_perm("view_image_metadata", staff_group, instance)
        if instance.public:
            public_group = Group.objects.get(name="Public")
            assign_perm("view_image", public_group, instance)
        contributor = instance.accession.cohort.contributor
        contributor_group = Group.objects.get(name=f"contributor_{contributor.id}")
        assign_perm("view_image", contributor_group, instance)
        assign_perm("view_image_metadata", contributor_group, instance)


@receiver(post_save, sender=ImageShare)
def image_share_save_assign_perms(sender, instance, created, **kwargs):
    if created:
        assign_perm("view_image", instance.grantee, instance.image)


@receiver(post_save, sender=Contributor)
def contributor_save_assign_perms(sender, instance, created, **kwargs):
    contributor_group, _ = Group.objects.get_or_create(name=f"contributor_{instance.id}")
    contributor_group.user_set.add(*instance.owners.all())
    contributor_images = Image.objects.filter(accession__cohort__contributor=instance.id)
    assign_perm("view_image", contributor_group, contributor_images)
    assign_perm("view_image_metadata", contributor_group, contributor_images)
