import pytest

from isic.core.forms.doi import CreateDoiForm
from isic.core.models.doi import Doi
from isic.core.models.image import Image


@pytest.fixture
def public_collection_with_public_images(image_factory, collection_factory):
    collection = collection_factory(public=True)
    collection.images.set([image_factory(public=True) for _ in range(5)])
    return collection


@pytest.fixture
def public_collection_with_private_images(image_factory, collection_factory):
    collection = collection_factory(public=True)
    collection.images.set([image_factory(public=False) for _ in range(5)])
    return collection


@pytest.fixture
def staff_user_request(staff_user, mocker):
    return mocker.MagicMock(user=staff_user)


@pytest.mark.django_db
def test_doi_form_requires_public_collection(private_collection, staff_user_request):
    form = CreateDoiForm(data={'collection_pk': private_collection.pk}, request=staff_user_request)
    assert not form.is_valid()


@pytest.mark.django_db
def test_doi_form_requires_all_public_images(
    public_collection_with_private_images, staff_user_request
):
    form = CreateDoiForm(
        data={'collection_pk': public_collection_with_private_images.pk}, request=staff_user_request
    )
    assert not form.is_valid()


@pytest.mark.django_db
def test_doi_form_requires_no_existing_doi(public_collection, staff_user_request):
    public_collection.doi = Doi.objects.create(id='foo', url='foo')
    public_collection.save()

    form = CreateDoiForm(
        data={'collection_pk': public_collection.pk},
        request=staff_user_request,
    )
    assert not form.is_valid()


@pytest.mark.django_db
def test_doi_form_creation(public_collection_with_public_images, staff_user_request, mocker):
    mocker.patch.object(CreateDoiForm, '_create_doi', lambda self: True)

    form = CreateDoiForm(
        data={'collection_pk': public_collection_with_public_images.pk},
        request=staff_user_request,
    )
    assert form.is_valid(), form.errors
    form.save()

    public_collection_with_public_images.refresh_from_db()
    assert public_collection_with_public_images.doi is not None


@pytest.fixture
def collection_with_several_creators(image_factory, collection_factory, cohort_factory):
    # Cohort A has the most images in collection
    # Cohort B and C have the same number of images in collection
    # Therefore, DOI creation should order A (most), then B and C (alphabetical tie breaker)
    cohort_a, cohort_b, cohort_c = (
        cohort_factory(attribution='Cohort A'),
        cohort_factory(attribution='Cohort B'),
        cohort_factory(attribution='Cohort C'),
    )
    collection = collection_factory(public=True)

    for _ in range(3):
        image_factory(public=True, accession__upload__cohort=cohort_a)

    for _ in range(2):
        image_factory(public=True, accession__upload__cohort=cohort_b)
        image_factory(public=True, accession__upload__cohort=cohort_c)

    collection.images.set(
        Image.objects.filter(accession__upload__cohort__in=[cohort_a, cohort_b, cohort_c])
    )

    return collection, cohort_a, cohort_b, cohort_c


@pytest.mark.django_db
def test_doi_creators_ordered_by_number_images_contributed(collection_with_several_creators, user):
    collection, cohort_a, cohort_b, cohort_c = collection_with_several_creators

    doi = collection.as_datacite_doi(user, 'foo')

    creators = doi['data']['attributes']['creators']

    assert creators[0]['name'] == cohort_a.attribution
    assert creators[1]['name'] == cohort_b.attribution
    assert creators[2]['name'] == cohort_c.attribution


@pytest.mark.skip
def test_doi_creators_order_anonymous_contributions_last():
    pass


@pytest.mark.skip
def test_doi_creators_collapse_multiple_anonymous_contributions():
    pass
