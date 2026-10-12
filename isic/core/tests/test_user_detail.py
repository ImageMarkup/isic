from operator import attrgetter

from django.contrib.auth.models import AnonymousUser
from django.template import Context, Template
from django.urls.base import reverse
from django.utils.html import escape
import pytest

from isic.core.views.users import USER_DETAIL_ROW_LIMIT
from isic.studies.tests.factories import AnnotationFactory, StudyTaskFactory


@pytest.mark.django_db
def test_user_detail_sections(
    staff_client,
    user,
    contributor_factory,
    cohort_factory,
    zip_upload_factory,
    accession_factory,
    engagement_accession_factory,
    engagement_profile_factory,
    metadata_file_factory,
    bulk_metadata_application_factory,
    metadata_version_factory,
    accession_review_factory,
    publish_request_factory,
    image_factory,
    collection_factory,
    collection_share_factory,
    image_share_factory,
    doi_factory,
    draft_doi_factory,
    segmentation_factory,
    segmentation_review_factory,
    study_factory,
    social_account_factory,
    faker,
):
    engagement_profile = engagement_profile_factory(user=user, provisioned=True)
    social_account = social_account_factory(user=user, email=faker.email())

    contributor = contributor_factory(creator=user)
    owned_contributor = contributor_factory(owners=[user])
    cohort = cohort_factory(contributor=contributor)
    zip_upload = zip_upload_factory(cohort=cohort)
    accession = accession_factory(zip_upload=zip_upload)
    single_accession = accession_factory(zip_upload=None, cohort=cohort)
    engagement_accession = engagement_accession_factory(
        accession=accession_factory(zip_upload=None, cohort=cohort)
    )
    metadata_file = metadata_file_factory(cohort=cohort)

    image = image_factory(creator=user)
    collection = collection_factory(creator=user)
    study = study_factory(creator=user)
    owned_study = study_factory(owners=[user])
    study_task = StudyTaskFactory(annotator=user, study=study, image=image)
    annotation = AnnotationFactory(annotator=user, study=study)
    segmentation = segmentation_factory(creator=user, image=image)

    # everything created implicitly by these factories belongs to someone else, which checks
    # that each section only lists what the user is linked to.
    cohort_factory()

    expected = {
        "contributors": {contributor.pk, owned_contributor.pk},
        "cohorts": {cohort.pk},
        "zip_uploads": {zip_upload.pk},
        "accessions": {accession.pk, single_accession.pk, engagement_accession.accession.pk},
        "metadata_files": {metadata_file.pk},
        "metadata_applications": {
            bulk_metadata_application_factory(creator=user, metadata_file=metadata_file).pk
        },
        "metadata_versions": {metadata_version_factory(creator=user, accession=accession).pk},
        "accession_reviews": {accession_review_factory(creator=user, accession=accession).pk},
        "publish_requests": {publish_request_factory(creator=user).pk},
        "published_images": {image.pk},
        "collections": {collection.pk},
        "collection_shares": {
            collection_share_factory(grantor=user, collection=collection).pk,
            collection_share_factory(grantee=user).pk,
        },
        "image_shares": {
            image_share_factory(grantor=user, image=image).pk,
            image_share_factory(grantee=user).pk,
        },
        "dois": {doi_factory(creator=user).pk},
        "draft_dois": {draft_doi_factory(creator=user).pk},
        "segmentations": {segmentation.pk},
        "segmentation_reviews": {
            segmentation_review_factory(creator=user, segmentation=segmentation).pk
        },
        "studies": {study.pk, owned_study.pk},
        "study_tasks": {study_task.pk, annotation.task.pk},
        "annotations": {annotation.pk},
    }

    url = reverse("core/user-detail", args=[user.pk])

    r = staff_client.get(url)
    assert r.status_code == 200
    counts = {
        entry.key: entry.count for _, entries in r.context["section_groups"] for entry in entries
    }
    assert counts == {key: len(pks) for key, pks in expected.items()}

    content = r.content.decode()
    assert user.email in content
    assert social_account.extra_data["email"] in content
    assert engagement_profile.default_cohort.name in content

    for key, pks in expected.items():
        r = staff_client.get(url, {"section": key})
        assert r.status_code == 200, key
        assert {listed.pk for listed in r.context["rows"]} == pks, key


@pytest.mark.django_db
def test_user_detail_without_records(staff_client, user):
    r = staff_client.get(reverse("core/user-detail", args=[user.pk]))

    assert r.context["section_groups"] == []
    assert "Nothing to show for this user." in r.content.decode()


@pytest.mark.django_db
def test_user_detail_row_limit(staff_client, user, collection_factory):
    collections = collection_factory.create_batch(USER_DETAIL_ROW_LIMIT + 1, creator=user)
    oldest = min(collections, key=attrgetter("created"))

    r = staff_client.get(reverse("core/user-detail", args=[user.pk]), {"section": "collections"})

    assert len(r.context["rows"]) == USER_DETAIL_ROW_LIMIT
    assert oldest not in r.context["rows"]
    assert (
        f"Showing the newest {USER_DETAIL_ROW_LIMIT} of {len(collections)}." in r.content.decode()
    )


@pytest.mark.django_db
def test_user_link_only_links_for_staff(rf, user, staff_user, nonstaff_user):
    template = Template("{% load display %}{% user_link linked_user linked_user.get_full_name %}")
    url = reverse("core/user-detail", args=[user.pk])

    for viewer, linked in [(staff_user, True), (nonstaff_user, False), (AnonymousUser(), False)]:
        request = rf.get("/")
        request.user = viewer
        html = template.render(Context({"request": request, "linked_user": user}))
        assert escape(user.get_full_name()) in html
        assert (url in html) is linked

    user.first_name = user.last_name = ""
    request.user = staff_user
    html = template.render(Context({"request": request, "linked_user": user}))
    assert escape(str(user)) in html
