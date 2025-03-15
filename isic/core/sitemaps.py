from django.contrib.sitemaps import Sitemap

from isic.core.models.collection import Collection
from isic.core.models.doi import Doi


class DoiSitemap(Sitemap):
    # TODO: change to monthly once DOI updates are more stable
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Doi.objects.all()


class PinnedCollectionSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Collection.objects.public().pinned()


sitemaps = {
    "dois": DoiSitemap,
    "pinned_collections": PinnedCollectionSitemap,
}
