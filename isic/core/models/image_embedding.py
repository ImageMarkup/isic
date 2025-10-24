from __future__ import annotations

from django.db import models
from pgvector.django import HalfVectorField, IvfflatIndex


class ImageEmbedding(models.Model):
    image = models.OneToOneField(
        "Image",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="embedding_relation",
    )
    embedding = HalfVectorField(dimensions=3584)

    class Meta:
        indexes = [
            IvfflatIndex(
                name="imageembedding_embed_ivfflat",
                fields=["embedding"],
                lists=1000,
                opclasses=["halfvec_cosine_ops"],
            ),
        ]

    def __str__(self):
        return f"Embedding for {self.image.isic_id}"
