from cachalot.api import cachalot_disabled
from django.urls import reverse
from isic_metadata.fields import ImageTypeEnum
import pytest
from pytest_lazy_fixtures import lf

from isic.core.dsl import es_parser, parse_query
from isic.core.search import (
    add_to_search_index,
    build_elasticsearch_query,
    facets,
    get_elasticsearch_client,
)


@pytest.fixture
def private_searchable_image(image_factory, _search_index):
    image = image_factory(public=False)
    add_to_search_index(image)

    # Ensure that the images are available in the index for search
    get_elasticsearch_client().indices.refresh(index="_all")

    return image


@pytest.fixture
def searchable_images(image_factory, _search_index):
    images = [
        image_factory(
            public=True,
            accession__short_diagnosis="melanoma",
        ),
        image_factory(
            public=False,
            accession__short_diagnosis="nevus",
        ),
    ]
    for image in images:
        add_to_search_index(image)

    # Ensure that the images are available in the index for search
    get_elasticsearch_client().indices.refresh(index="_all")

    return images


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route",
    ["api:search_images", "api:list_images"],
)
def test_elasticsearch_counts(searchable_images, settings, client, route):
    settings.ISIC_USE_ELASTICSEARCH_COUNTS = False

    r = client.get(reverse(route))
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1, r.json()

    settings.ISIC_USE_ELASTICSEARCH_COUNTS = True

    r = client.get(reverse(route))
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1, r.json()


@pytest.fixture
def searchable_image_with_private_field(image_factory, _search_index):
    image = image_factory(public=True, accession__age=50)
    add_to_search_index(image)

    # Ensure that the images are available in the index for search
    get_elasticsearch_client().indices.refresh(index="_all")

    return image


@pytest.fixture
def private_and_public_images_collections(image_factory, collection_factory, _search_index):
    public_coll, private_coll = collection_factory(public=True), collection_factory(public=False)
    public_image, private_image = (
        image_factory(public=True, accession__age=10),
        image_factory(public=False),
    )

    public_coll.images.add(public_image)
    private_coll.images.add(private_image)

    for image in [public_image, private_image]:
        add_to_search_index(image)

    get_elasticsearch_client().indices.refresh(index="_all")

    return public_coll, private_coll


@pytest.fixture
def collection_with_image(_search_index, image_factory, collection_factory):
    public_coll = collection_factory(public=True)
    public_image = image_factory(public=True, accession__age=52)
    public_coll.images.add(public_image)
    add_to_search_index(public_image)
    get_elasticsearch_client().indices.refresh(index="_all")
    return public_coll


@pytest.mark.django_db
def test_elasticsearch_caching(searchable_images, settings, staff_client, client, mocker):
    # using elasticsearch counts is the easiest way to test elasticsearch caching
    settings.ISIC_USE_ELASTICSEARCH_COUNTS = True

    import isic.core.search

    cache_get = mocker.spy(isic.core.search.cache, "get")
    cache_set = mocker.spy(isic.core.search.cache, "set")

    with cachalot_disabled():
        r = staff_client.get("/api/v2/images/search/")
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == 2, r.json()
        assert cache_get.call_count == 1
        assert cache_set.call_count == 1

        r = staff_client.get("/api/v2/images/search/")
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == 2, r.json()
        assert cache_get.call_count == 2
        assert cache_set.call_count == 1

        # notably the cache is not shared between a staff user and a regular user
        r = client.get("/api/v2/images/search/")
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == 1, r.json()
        assert cache_get.call_count == 3
        assert cache_set.call_count == 2

    # make sure all of the calls are related to elasticsearch caching
    for call in cache_get.mock_calls + cache_set.mock_calls:
        assert call.args[0].startswith("es:")


@pytest.mark.django_db
def test_elasticsearch_cache_sharing(
    searchable_images, client, user_factory, settings, mocker, contributor_factory
):
    # using elasticsearch counts is the easiest way to test elasticsearch caching
    settings.ISIC_USE_ELASTICSEARCH_COUNTS = True

    import isic.core.search

    cache_get = mocker.spy(isic.core.search.cache, "get")
    cache_set = mocker.spy(isic.core.search.cache, "set")

    with cachalot_disabled():
        r = client.get("/api/v2/images/search/")
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == 1, r.json()
        assert cache_get.call_count == 1
        assert cache_set.call_count == 1

        user = user_factory()
        client.force_login(user)

        # a public user shares the same cache with a regular user with no special permissions
        r = client.get("/api/v2/images/search/")
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == 1, r.json()
        assert cache_get.call_count == 2
        assert cache_set.call_count == 1

        contributor = contributor_factory()
        user.owned_contributors.add(contributor)

        # now the user has special permissions, so the cache should not be shared
        r = client.get("/api/v2/images/search/")
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == 1, r.json()
        assert cache_get.call_count == 3
        assert cache_set.call_count == 2

    # make sure all of the calls are related to elasticsearch caching
    for call in cache_get.mock_calls + cache_set.mock_calls:
        assert call.args[0].startswith("es:")


@pytest.mark.django_db
def test_core_api_image_search(searchable_images, staff_client):
    r = staff_client.get("/api/v2/images/search/")
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 2, r.json()

    r = staff_client.get("/api/v2/images/search/", {"query": "diagnosis_3:Nevus"})
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1, r.json()


@pytest.mark.django_db
def test_core_api_image_search_private_image(private_searchable_image, authenticated_client):
    r = authenticated_client.get("/api/v2/images/search/")
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 0, r.json()


@pytest.mark.django_db
def test_core_api_image_search_private_image_as_guest(private_searchable_image, client):
    r = client.get("/api/v2/images/search/")
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 0, r.json()


@pytest.mark.django_db
def test_core_api_image_search_images_as_guest(searchable_images, client):
    r = client.get("/api/v2/images/search/")
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1, r.json()


@pytest.mark.django_db
def test_core_api_image_search_contributed(private_searchable_image, authenticated_client, user):
    private_searchable_image.accession.cohort.contributor.owners.add(user)
    add_to_search_index(private_searchable_image)
    get_elasticsearch_client().indices.refresh(index="_all")

    r = authenticated_client.get("/api/v2/images/search/")
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1, r.json()


@pytest.mark.django_db
def test_core_api_image_search_shares(
    private_searchable_image, authenticated_client, user, staff_user
):
    private_searchable_image.shares.add(user, through_defaults={"grantor": staff_user})
    private_searchable_image.save()
    add_to_search_index(private_searchable_image)
    get_elasticsearch_client().indices.refresh(index="_all")

    r = authenticated_client.get("/api/v2/images/search/")
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1, r.json()


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["images/search/", "images/facets/"])
def test_core_api_image_search_invalid_query(route, searchable_images, authenticated_client):
    r = authenticated_client.get(f"/api/v2/{route}", {"query": "age_approx:[[[[]]]]"})
    assert r.status_code == 400, r.json()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route",
    ["/api/v2/images/", "/api/v2/images/search/"],
)
def test_core_api_image_hides_fields(
    authenticated_client, searchable_image_with_private_field, route
):
    r = authenticated_client.get(route)
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1, r.json()
    for image in r.json()["results"]:
        assert "age" not in image["metadata"]


@pytest.mark.django_db
def test_core_api_image_search_collection_and_query(collection_with_image, authenticated_client):
    r = authenticated_client.get(
        "/api/v2/images/search/",
        {"collections": f"{collection_with_image.pk}", "query": "age_approx:50"},
    )
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1, r.json()


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
@pytest.mark.parametrize(
    ("collection_is_public", "image_is_public", "can_see"),
    [
        (True, True, True),
        # Don't leak which images are in a private collection
        (False, True, False),
        (False, False, False),
    ],
    ids=["all-public", "private-coll-public-image", "all-private"],
)
def test_core_api_image_search_collection(
    authenticated_client,
    image_factory,
    collection_factory,
    collection_is_public,
    image_is_public,
    can_see,
):
    collection = collection_factory(public=collection_is_public)
    image = image_factory(public=image_is_public)
    collection.images.add(image)
    add_to_search_index(image)
    get_elasticsearch_client().indices.refresh(index="_all")

    r = authenticated_client.get("/api/v2/images/search/", {"collections": str(collection.pk)})
    assert r.status_code == 200, r.json()

    if can_see:
        assert r.json()["count"] == 1, r.json()
    else:
        assert r.json()["count"] == 0, r.json()


@pytest.mark.django_db
def test_core_api_image_search_collection_parsing(
    private_and_public_images_collections, authenticated_client
):
    public_coll, private_coll = private_and_public_images_collections

    r = authenticated_client.get(
        "/api/v2/images/search/", {"collections": f"{public_coll.pk},{private_coll.pk}"}
    )
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1, r.json()


@pytest.mark.django_db
def test_core_api_image_faceting_collection_filter(private_and_public_images_collections, client):
    public_coll, _ = private_and_public_images_collections

    r = client.get("/api/v2/images/facets/", {"collections": f"{public_coll.pk}"})
    assert r.status_code == 200, r.json()

    for bucket in r.json()["age_approx"]["buckets"]:
        if bucket["key"] == 10.0:
            assert bucket["doc_count"] == 1
        else:
            assert bucket["doc_count"] == 0


@pytest.mark.django_db
def test_core_api_image_faceting_structure(searchable_images, client):
    r = client.get(
        "/api/v2/images/facets/",
    )
    assert r.status_code == 200, r.json()
    assert len(r.json()["diagnosis_3"]["buckets"]) == 2, r.json()
    assert r.json()["diagnosis_3"]["meta"] == {
        "missing_count": 0,
        "present_count": 1,
    }, r.json()


@pytest.mark.parametrize(
    "client_",
    [
        lf("client"),
        lf("authenticated_client"),
    ],
)
@pytest.mark.django_db
def test_core_api_image_faceting_query(private_and_public_images_collections, client_):
    public_coll, private_coll = private_and_public_images_collections

    r = client_.get("/api/v2/images/facets/", {"query": "age_approx:10"})
    assert r.status_code == 200, r.json()
    buckets = r.json()["age_approx"]["buckets"]
    for bucket in buckets:
        if bucket["key"] == 10.0:
            assert bucket["doc_count"] == 1
        else:
            assert bucket["doc_count"] == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_facet_search_orders_field_values(image_factory):
    # it's important to create the an image with a later ordered image type first
    # to make sure it's not ordering it correctly on accident.
    image = image_factory(public=True, accession__image_type="TBP tile: close-up")
    add_to_search_index(image)

    # Ensure that the images are available in the index for search
    get_elasticsearch_client().indices.refresh(index="_all")

    actual = facets()

    for i, image_type in enumerate(ImageTypeEnum):
        assert actual["image_type"]["buckets"][i]["key"] == image_type.value


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_facet_search_includes_empty_facet_values(user, image_factory):
    image = image_factory(public=True, accession__anatom_site_special="toenail")
    add_to_search_index(image)
    get_elasticsearch_client().indices.refresh(index="_all")

    es_query = parse_query(es_parser, "-anatom_site_special:toenail")
    query = build_elasticsearch_query(es_query, user)

    get_elasticsearch_client().indices.refresh(index="_all")
    actual = facets(query)

    assert actual["anatom_site_special"]["buckets"][0]["key"] == "toenail"
    assert actual["anatom_site_special"]["buckets"][0]["doc_count"] == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_facet_search_includes_missing_field_values(image_factory):
    actual = facets()

    for image_type in ImageTypeEnum:
        assert any(bucket["key"] == image_type.value for bucket in actual["image_type"]["buckets"])
