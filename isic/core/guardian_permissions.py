from django.contrib.auth.models import Group, User
from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm

from isic.core.models.image import Image, ImageShare
from isic.ingest.models import Contributor

STAFF_GROUP_NAME = "ISIC Staff"
PUBLIC_GROUP_NAME = "Public"


def get_contributor_group_name(contributor):
    return f"contributor_{contributor.id}"


def assign_image_perms():
    all_images = Image.objects.all()
    public_images = Image.objects.filter(public=True)
    staff_group = Group.objects.get(name=STAFF_GROUP_NAME)
    public_group = Group.objects.get(name=PUBLIC_GROUP_NAME)
    assign_perm("view_image", public_group, public_images)
    assign_perm("view_image", staff_group, all_images)
    assign_perm("view_image_metadata", staff_group, all_images)
    for image_share in ImageShare.objects.all():
        assign_perm("view_image", image_share.grantee, image_share.image)
    for contributor in Contributor.objects.all():
        contributor_group = Group.objects.get(name=get_contributor_group_name(contributor))
        contributor_images = Image.objects.filter(accession__cohort__contributor=contributor.id)
        assign_perm("view_image", contributor_group, contributor_images)
        assign_perm("view_image_metadata", contributor_group, contributor_images)


@receiver(post_save, sender=User)
def user_save_assign_groups(sender, instance, created, **kwargs):
    instance.groups.clear()

    public_group, _ = Group.objects.get_or_create(name=PUBLIC_GROUP_NAME)
    instance.groups.add(public_group)

    if instance.is_staff:
        staff_group, _ = Group.objects.get_or_create(name=STAFF_GROUP_NAME)
        instance.groups.add(staff_group)

    for contributor in instance.owned_contributors.all():
        contributor_group, _  = Group.objects.get_or_create(
            name=get_contributor_group_name(contributor)
        )
        instance.groups.add(contributor_group)


@receiver(post_save, sender=Image)
def image_save_assign_perms(sender, instance, created, **kwargs):
    if created:
        staff_group = Group.objects.get(name=STAFF_GROUP_NAME)
        assign_perm("view_image", staff_group, instance)
        assign_perm("view_image_metadata", staff_group, instance)
        if instance.public:
            public_group = Group.objects.get(name=PUBLIC_GROUP_NAME)
            assign_perm("view_image", public_group, instance)
        contributor = instance.accession.cohort.contributor
        contributor_group = Group.objects.get(name=get_contributor_group_name(contributor))
        assign_perm("view_image", contributor_group, instance)
        assign_perm("view_image_metadata", contributor_group, instance)


@receiver(post_save, sender=ImageShare)
def image_share_save_assign_perms(sender, instance, created, **kwargs):
    if created:
        assign_perm("view_image", instance.grantee, instance.image)


@receiver(post_save, sender=Contributor)
def contributor_save_assign_perms(sender, instance, created, **kwargs):
    contributor_group, _ = Group.objects.get_or_create(name=get_contributor_group_name(instance))
    contributor_group.user_set.add(*instance.owners.all())
    contributor_images = Image.objects.filter(accession__cohort__contributor=instance.id)
    assign_perm("view_image", contributor_group, contributor_images)
    assign_perm("view_image_metadata", contributor_group, contributor_images)
