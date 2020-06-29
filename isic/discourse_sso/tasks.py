from celery import shared_task

from isic.discourse_sso.models import Image


@shared_task()
def image_compute_checksum(image_id: int):
    image = Image.objects.get(pk=image_id)
    image.checksum = image.compute_checksum()
    image.save()
