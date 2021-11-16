import django.apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
import djclick as click


@click.command(help='Add ISIC Staff group with basic view permissions')
def add_staff_group():
    group, _ = Group.objects.get_or_create(name='ISIC Staff')

    for model in django.apps.apps.get_models():
        if model.__module__.startswith('isic.'):  # TODO: hacky?
            content_type = ContentType.objects.get_for_model(model)
            for permission in ['view']:
                group.permissions.add(
                    Permission.objects.get(
                        codename=f'{permission}_{content_type.model}',
                        content_type=content_type,
                    )
                )
