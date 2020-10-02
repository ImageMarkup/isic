from django.apps import AppConfig


class StudiesConfig(AppConfig):
    name = 'isic.studies'
    verbose_name = 'ISIC: Studies'

    def ready(self):
        from django.contrib.auth.models import Group
        from guardian.shortcuts import assign_perm

        isic_core, _ = Group.objects.get_or_create(name='ISIC Core')
        assign_perm('studies.view_study', isic_core)
        assign_perm('studies.view_annotation', isic_core)

        study_admins, _ = Group.objects.get_or_create(name='Study admins')
        for action in ['add', 'change', 'delete', 'view']:
            for model in ['study', 'annotation']:
                assign_perm(f'studies.{action}_{model}', study_admins)
