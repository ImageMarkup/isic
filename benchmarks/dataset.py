"""
A fixed synthetic dataset, generated from SEED so every commit is benchmarked against the same rows.

Proportions loosely follow production: about 46% of images are public, one non-staff user has a
fifth of the images shared with them, and one collection holds three quarters of all images.
"""

from datetime import UTC, datetime
import hashlib
from pathlib import Path
import random
from typing import Literal, get_args

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
import numpy as np

import isic
from isic.core.models import Collection, Doi, Image, ImageEmbedding, IsicId
from isic.core.models.collection import CollectionImage, CollectionShare
from isic.core.models.image import ImageShare
from isic.ingest.models import Accession, AccessionStatus, Cohort, Contributor, Lesion, Patient
from isic.ingest.models.accession_review import AccessionReview
from isic.ingest.models.metadata_version import MetadataVersion
from isic.ingest.models.unstructured_metadata import UnstructuredMetadata
from isic.login.models import Profile
from isic.studies.models import (
    Annotation,
    Question,
    QuestionChoice,
    Response,
    Study,
    StudyQuestion,
    StudyTask,
)

SEED = 1
EPOCH = datetime(2016, 1, 1, tzinfo=UTC)

NamedUser = Literal["staff", "shares", "owner", "user"]
NAMED_USERS: tuple[NamedUser, ...] = get_args(NamedUser)
# not logged in, or logged in as a named user
Viewer = Literal["anonymous"] | NamedUser
# the users most benchmarks run as
USERS: list[Viewer] = ["anonymous", "shares", "staff"]
ANNOTATORS = 10
EXTRA_USERS = 200

PUBLISHED_ACCESSIONS = 100_000
UNPUBLISHED_ACCESSIONS = 5_000
IMAGE_SHARES = 20_000
EMBEDDINGS = 2_000
PINNED_IMAGES = 20

# (percentage of published accessions, fraction of them that is public)
COHORTS = [
    (40, 0.5),
    (20, 0.0),
    (10, 1.0),
    (10, 0.5),
    (5, 1.0),
    (5, 0.0),
    (4, 0.5),
    (3, 1.0),
    (2, 0.0),
    (1, 1.0),
]
CONTRIBUTORS = 5
OWNED_CONTRIBUTOR = 1
INGEST_COHORT = "Benchmark Ingest"

PATIENT_SIZES = [1, 1, 1, 2, 2, 3, 5, 8, 13, 30, 100]
LESION_SIZES = [1, 1, 2, 3, 5, 10]
SHOWCASE_PATIENT_SIZE = 300
SHOWCASE_LESION_SIZE = 10
SHOWCASE_ISIC_ID = "ISIC_0000000"
SHOWCASE_LESION_ID = "IL_0000000"

COLLECTIONS = {
    "all_public": "Benchmark All Public",
    "large": "Benchmark Large",
    "medium": "Benchmark Medium",
    "small": "Benchmark Small",
    "target": "Benchmark Target",
}
LARGE_COLLECTION_IMAGES = 75_000
MEDIUM_COLLECTION_IMAGES = 10_000
SMALL_COLLECTION_IMAGES = 1_000
MISC_COLLECTIONS = 40
MISC_COLLECTION_SIZES = [10, 50, 100, 500, 2_000]
DOI_SLUG = "benchmark-medium"

PUBLIC_STUDY = "Benchmark Public Study"
PRIVATE_STUDY = "Benchmark Private Study"

# the most common value combinations in production, as (weight, values)
DIAGNOSES = [
    (60, ("Benign", None, None, None, None)),
    (12, ("Benign", "Benign melanocytic proliferations", "Nevus", None, None)),
    (8, (None, None, None, None, None)),
    (
        5,
        (
            "Malignant",
            "Malignant adnexal epithelial proliferations - Follicular",
            "Basal cell carcinoma",
            None,
            None,
        ),
    ),
    (
        4,
        (
            "Malignant",
            "Malignant melanocytic proliferations (Melanoma)",
            "Melanoma, NOS",
            None,
            None,
        ),
    ),
    (
        3,
        (
            "Benign",
            "Benign melanocytic proliferations",
            "Nevus",
            "Nevus, Atypical, Dysplastic, or Clark",
            "Nevus, Dysplastic",
        ),
    ),
    (2, ("Benign", "Benign epidermal proliferations", "Seborrheic keratosis", None, None)),
    (
        2,
        ("Benign", "Benign melanocytic proliferations", "Nevus", "Nevus, NOS, Compound", None),
    ),
    (
        2,
        (
            "Indeterminate",
            "Indeterminate epidermal proliferations",
            "Solar or actinic keratosis",
            None,
            None,
        ),
    ),
    (
        2,
        (
            "Malignant",
            "Malignant epidermal proliferations",
            "Squamous cell carcinoma, NOS",
            None,
            None,
        ),
    ),
]
ANATOM_SITES = [
    (25, ("Lower extremity", None, None)),
    (15, ("Trunk", "Anterior trunk", None)),
    (13, ("Trunk", "Posterior trunk", "Upper back")),
    (9, ("Upper extremity", "Upper arm", None)),
    (8, ("Upper extremity", None, None)),
    (8, ("Trunk", "Posterior trunk", "Mid back")),
    (7, (None, None, None)),
    (5, ("Trunk", "Posterior trunk", None)),
]
IMAGE_TYPES = [
    (60, ("TBP tile: close-up", None, "3D: XP")),
    (15, ("TBP tile: close-up", None, "3D: white")),
    (12, ("dermoscopic", None, None)),
    (7, ("dermoscopic", "contact polarized", None)),
    (4, ("dermoscopic", "contact non-polarized", None)),
    (1, ("clinical: close-up", None, None)),
    (1, ("TBP tile: overview", None, "3D: XP")),
]
CONFIRMATIONS = [
    (60, (None, None, None)),
    (16, ("single contributor clinical assessment", False, None)),
    (6, (None, False, True)),
    (5, ("serial imaging showing no change", False, None)),
    (4, (None, False, None)),
    (3, ("histopathology", True, True)),
    (2, ("single image expert consensus", False, None)),
    (1, ("histopathology", True, False)),
]
SEXES = [(60, "male"), (30, "female"), (10, None)]
FITZPATRICK_SKIN_TYPES = [(95, None), (2, "II"), (1, "I"), (1, "III"), (1, "IV")]
LICENSES = [(46, "CC-BY"), (45, "CC-BY-NC"), (9, "CC-0")]
STATUSES = [
    (90, AccessionStatus.SUCCEEDED),
    (5, AccessionStatus.FAILED),
    (5, AccessionStatus.SKIPPED),
]


def template_name() -> str:
    """
    Name the database that keeps a generated dataset.

    It's named after the migrations and this file, so it's only reused for the same schema and
    data.
    """
    return f"{connection.settings_dict['TEST']['NAME']}_{_dataset_key()}"


def template_exists() -> bool:
    with connection._nodb_cursor() as cursor:  # noqa: SLF001
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [template_name()])
        return cursor.fetchone() is not None


def generate() -> None:
    """Generate the dataset into the migrated test database and keep a copy of it."""
    _build()
    connection.creation.clone_test_db(suffix=_dataset_key(), verbosity=0, keepdb=True)


def manifest() -> dict:
    return {
        "users": {name: User.objects.get(username=f"benchmark-{name}").pk for name in NAMED_USERS},
        "collections": {
            key: Collection.objects.get(name=name).pk for key, name in COLLECTIONS.items()
        },
        "doi_slug": DOI_SLUG,
        "public_study": Study.objects.get(name=PUBLIC_STUDY).pk,
        "ingest_cohort": Cohort.objects.get(name=INGEST_COHORT).pk,
    }


def _dataset_key() -> str:
    digest = hashlib.sha256(Path(__file__).read_bytes())
    for migration in sorted(Path(isic.__file__).parent.glob("*/migrations/*.py")):
        digest.update(migration.read_bytes())
    return digest.hexdigest()[:16]


def _pick(rng: random.Random, choices: list[tuple[int, object]]):
    return rng.choices([value for _, value in choices], [weight for weight, _ in choices])[0]


def _metadata(rng: random.Random) -> dict:
    diagnosis = _pick(rng, DIAGNOSES)
    anatom_site = _pick(rng, ANATOM_SITES)
    image_type, dermoscopic_type, tbp_tile_type = _pick(rng, IMAGE_TYPES)
    confirm_type, concomitant_biopsy, melanocytic = _pick(rng, CONFIRMATIONS)
    return {
        **{f"diagnosis_{i}": value for i, value in enumerate(diagnosis, start=1)},
        **{f"anatom_site_{i}": value for i, value in enumerate(anatom_site, start=1)},
        "image_type": image_type,
        "dermoscopic_type": dermoscopic_type,
        "tbp_tile_type": tbp_tile_type,
        "diagnosis_confirm_type": confirm_type,
        "concomitant_biopsy": concomitant_biopsy,
        "melanocytic": melanocytic,
        "sex": _pick(rng, SEXES),
        "age": None if rng.random() < 0.1 else rng.randint(0, 85),
        "fitzpatrick_skin_type": _pick(rng, FITZPATRICK_SKIN_TYPES),
        "copyright_license": _pick(rng, LICENSES),
    }


def _build() -> None:
    rng = random.Random(SEED)

    users = _create_users()
    staff = users["staff"]
    cohorts, ingest_cohort = _create_cohorts(users)
    published, unpublished = _create_accessions(rng, staff, cohorts, ingest_cohort)
    images = _create_images(published, staff)
    _create_reviews(rng, staff, published, unpublished)
    _create_unstructured_metadata(rng, [*published, *unpublished])
    _create_metadata_versions(staff, published[0])
    _set_created_times()

    public_ids = [image.pk for image in images if image.public]
    private_ids = [image.pk for image in images if not image.public]
    collections = _create_collections(rng, users, [image.pk for image in images], public_ids)
    _create_shares(rng, users, private_ids, collections)
    _create_embeddings(public_ids[:EMBEDDINGS])
    _create_studies(rng, users, collections)

    with connection.cursor() as cursor:
        cursor.execute("REINDEX TABLE core_imageembedding")
        cursor.execute("REFRESH MATERIALIZED VIEW materialized_collection_counts")
        cursor.execute("VACUUM ANALYZE")


def _create_users() -> dict[str, User]:
    names = [
        *NAMED_USERS,
        *(f"annotator-{i}" for i in range(ANNOTATORS)),
        *(f"user-{i}" for i in range(EXTRA_USERS)),
    ]
    users = {
        name: User.objects.create_user(
            username=f"benchmark-{name}",
            email=f"benchmark-{name}@example.com",
            first_name="Benchmark",
            last_name=name,
            is_staff=name == "staff",
            is_superuser=name == "staff",
        )
        for name in names
    }
    Profile.objects.update(accepted_terms=EPOCH)
    return users


def _create_cohorts(users: dict[str, User]) -> tuple[list[Cohort], Cohort]:
    staff = users["staff"]
    contributors = [
        Contributor.objects.create(
            creator=staff,
            institution_name=f"Benchmark Institution {i}",
            legal_contact_info="Benchmark",
            default_copyright_license="CC-BY",
            default_attribution=f"Benchmark Institution {i}",
        )
        for i in range(CONTRIBUTORS)
    ]
    contributors[OWNED_CONTRIBUTOR].owners.add(users["owner"])

    def cohort(name: str, contributor: Contributor) -> Cohort:
        return Cohort.objects.create(
            contributor=contributor,
            creator=staff,
            name=name,
            description=name,
            default_copyright_license="CC-BY",
            default_attribution=contributor.default_attribution,
        )

    cohorts = [
        cohort(f"Benchmark Cohort {i}", contributors[i % CONTRIBUTORS]) for i in range(len(COHORTS))
    ]
    return cohorts, cohort(INGEST_COHORT, contributors[0])


def _create_accessions(
    rng: random.Random, staff: User, cohorts: list[Cohort], ingest_cohort: Cohort
) -> tuple[list[Accession], list[Accession]]:
    patients: list[Patient] = []
    lesions: list[Lesion] = []
    published: list[Accession] = []

    def accession(n: int, cohort: Cohort, **kwargs) -> Accession:
        return Accession(
            creator=staff,
            cohort=cohort,
            attribution=cohort.default_attribution,
            original_blob=f"original/IMG_{n:07}.jpg",
            original_blob_name=f"IMG_{n:07}.jpg",
            original_blob_size=rng.randint(1_000_000, 20_000_000),
            **_metadata(rng),
            **kwargs,
        )

    def stored(n: int, *, public: bool) -> dict:
        blob, thumbnail = f"images/ISIC_{n:07}.jpg", f"thumbnails/ISIC_{n:07}.jpg"
        return {
            "status": AccessionStatus.SUCCEEDED,
            "blob": "" if public else blob,
            "thumbnail_256": "" if public else thumbnail,
            "sponsored_blob": blob if public else "",
            "sponsored_thumbnail_256_blob": thumbnail if public else "",
            "blob_size": rng.randint(200_000, 5_000_000),
            "thumbnail_256_size": rng.randint(5_000, 30_000),
            "width": 1024,
            "height": 768,
        }

    for cohort_index, (cohort, (percentage, public_fraction)) in enumerate(
        zip(cohorts, COHORTS, strict=True)
    ):
        remaining = PUBLISHED_ACCESSIONS * percentage // 100
        showcase = cohort_index == 0

        while remaining:
            size = min(remaining, SHOWCASE_PATIENT_SIZE if showcase else rng.choice(PATIENT_SIZES))
            patient = None
            if showcase or rng.random() < 0.75:
                patient = Patient(
                    id=f"IP_{len(patients):07}",
                    cohort=cohort,
                    private_patient_id=f"patient-{len(patients)}",
                )
                patients.append(patient)

            lesion, lesion_remaining = None, 0
            for _ in range(size):
                if patient and not lesion_remaining:
                    lesion_remaining = (
                        SHOWCASE_LESION_SIZE if showcase else rng.choice(LESION_SIZES)
                    )
                    lesion = Lesion(
                        id=f"IL_{len(lesions):07}",
                        cohort=cohort,
                        private_lesion_id=f"lesion-{len(lesions)}",
                    )
                    lesions.append(lesion)
                lesion_remaining -= 1

                n = len(published)
                public = showcase or rng.random() < public_fraction
                published.append(
                    accession(n, cohort, patient=patient, lesion=lesion, **stored(n, public=public))
                )

            remaining -= size
            showcase = False

    unpublished = []
    for n in range(len(published), len(published) + UNPUBLISHED_ACCESSIONS):
        status = _pick(rng, STATUSES)
        kwargs = (
            {**stored(n, public=False), "blob": f"images/IMG_{n:07}.jpg"}
            if status == AccessionStatus.SUCCEEDED
            else {"status": status}
        )
        unpublished.append(accession(n, ingest_cohort, **kwargs))

    Patient.objects.bulk_create(patients, batch_size=5_000)
    Lesion.objects.bulk_create(lesions, batch_size=5_000)
    Accession.objects.bulk_create([*published, *unpublished], batch_size=5_000)
    return published, unpublished


def _create_images(published: list[Accession], staff: User) -> list[Image]:
    isic_ids = IsicId.objects.bulk_create(
        (IsicId(id=f"ISIC_{n:07}") for n in range(len(published))), batch_size=5_000
    )
    images = [
        Image(
            accession=accession,
            isic=isic_id,
            creator=staff,
            public=bool(accession.sponsored_blob),
        )
        for accession, isic_id in zip(published, isic_ids, strict=True)
    ]
    for pinned, image in enumerate(
        (image for image in images[SHOWCASE_PATIENT_SIZE:] if image.public), start=1
    ):
        if pinned > PINNED_IMAGES:
            break
        image.pinned = pinned
    return Image.objects.bulk_create(images, batch_size=5_000)


def _create_reviews(
    rng: random.Random, staff: User, published: list[Accession], unpublished: list[Accession]
) -> None:
    reviewed = [
        *((accession, True) for accession in published),
        *(
            (accession, rng.random() < 0.8)
            for accession in unpublished
            if accession.status == AccessionStatus.SUCCEEDED and rng.random() < 0.5
        ),
    ]
    AccessionReview.objects.bulk_create(
        (
            AccessionReview(accession=accession, creator=staff, reviewed_at=EPOCH, value=value)
            for accession, value in reviewed
        ),
        batch_size=5_000,
    )


def _create_unstructured_metadata(rng: random.Random, accessions: list[Accession]) -> None:
    UnstructuredMetadata.objects.bulk_create(
        (
            UnstructuredMetadata(
                accession=accession,
                value=(
                    {"device": f"device-{rng.randint(0, 9)}", "site": f"site-{rng.randint(0, 99)}"}
                    if rng.random() < 0.3
                    else {}
                ),
            )
            for accession in accessions
        ),
        batch_size=5_000,
    )


def _create_metadata_versions(staff: User, accession: Accession) -> None:
    MetadataVersion.objects.bulk_create(
        MetadataVersion(
            creator=staff,
            accession=accession,
            metadata={**accession.metadata, "age": 30 + version},
            unstructured_metadata={"revision": version},
        )
        for version in range(5)
    )


def _set_created_times() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ingest_accession SET created = %s + id * interval '1 minute'", [EPOCH]
        )
        cursor.execute(
            """
            UPDATE core_image SET created = a.created + interval '30 days'
            FROM ingest_accession a WHERE a.id = core_image.accession_id
            """
        )


def _create_collections(
    rng: random.Random, users: dict[str, User], image_ids: list[int], public_ids: list[int]
) -> dict[str, Collection]:
    staff = users["staff"]

    def collection(name, creator, ids, *, public, pinned=False, locked=False) -> Collection:
        created = Collection.objects.create(
            creator=creator, name=name, public=public, pinned=pinned, locked=locked
        )
        CollectionImage.objects.bulk_create(
            (CollectionImage(collection=created, image_id=pk) for pk in ids), batch_size=5_000
        )
        return created

    collections = {
        "all_public": collection(
            COLLECTIONS["all_public"], staff, public_ids, public=True, pinned=True
        ),
        "large": collection(
            COLLECTIONS["large"],
            staff,
            sorted(rng.sample(image_ids, LARGE_COLLECTION_IMAGES)),
            public=False,
        ),
        "medium": collection(
            COLLECTIONS["medium"],
            staff,
            sorted(rng.sample(public_ids, MEDIUM_COLLECTION_IMAGES)),
            public=True,
            locked=True,
        ),
        "small": collection(
            COLLECTIONS["small"],
            staff,
            [public_ids[0], *sorted(rng.sample(public_ids[1:], SMALL_COLLECTION_IMAGES - 1))],
            public=True,
        ),
        "target": collection(COLLECTIONS["target"], staff, [], public=False),
    }

    creators = [staff, users["owner"], users["user"], users["shares"]]
    for i in range(MISC_COLLECTIONS):
        public = i % 2 == 0
        collections[f"misc-{i}"] = collection(
            f"Benchmark Collection {i}",
            creators[i % len(creators)],
            sorted(
                rng.sample(public_ids if public else image_ids, rng.choice(MISC_COLLECTION_SIZES))
            ),
            public=public,
        )

    Doi.objects.create(
        id=f"{settings.ISIC_DATACITE_DOI_PREFIX}/100000",
        slug=DOI_SLUG,
        collection=collections["medium"],
        creator=staff,
    )
    return collections


def _create_shares(
    rng: random.Random,
    users: dict[str, User],
    private_ids: list[int],
    collections: dict[str, Collection],
) -> None:
    staff, grantee = users["staff"], users["shares"]
    shared_collections = [collections["target"]] + [
        collection
        for key, collection in collections.items()
        if key.startswith("misc-") and int(key.removeprefix("misc-")) % 5 == 1
    ]
    CollectionShare.objects.bulk_create(
        CollectionShare(grantor=staff, grantee=grantee, collection=collection)
        for collection in shared_collections
    )

    shared_ids = set(rng.sample(private_ids, IMAGE_SHARES))
    shared_ids.update(
        CollectionImage.objects.filter(
            collection__in=shared_collections, image__public=False
        ).values_list("image_id", flat=True)
    )
    ImageShare.objects.bulk_create(
        (ImageShare(grantor=staff, grantee=grantee, image_id=pk) for pk in sorted(shared_ids)),
        batch_size=5_000,
    )


def _create_embeddings(image_ids: list[int]) -> None:
    vectors = np.random.default_rng(SEED).standard_normal((len(image_ids), 3584))
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    ImageEmbedding.objects.bulk_create(
        (
            ImageEmbedding(image_id=pk, embedding=vector.astype(np.float16))
            for pk, vector in zip(image_ids, vectors, strict=True)
        ),
        batch_size=200,
    )


def _create_studies(
    rng: random.Random, users: dict[str, User], collections: dict[str, Collection]
) -> None:
    staff = users["staff"]
    annotators = [users[f"annotator-{i}"] for i in range(ANNOTATORS)]
    questions = []
    for prompt, choices in [
        ("Benchmark: Is this lesion benign or malignant?", ["Benign", "Malignant", "Unsure"]),
        ("Benchmark: How confident are you?", ["Low", "Medium", "High"]),
    ]:
        question = Question.objects.create(prompt=prompt, type="select", official=False)
        QuestionChoice.objects.bulk_create(
            QuestionChoice(question=question, text=text) for text in choices
        )
        questions.append((question, list(question.choices.all())))

    def study(name, collection, annotators, *, public, annotated_fraction) -> None:
        created = Study.objects.create(
            creator=staff,
            attribution="Benchmark",
            name=name,
            description=name,
            collection=collection,
            public=public,
        )
        created.owners.add(staff)
        StudyQuestion.objects.bulk_create(
            StudyQuestion(study=created, question=question, order=order, required=True)
            for order, (question, _) in enumerate(questions)
        )
        image_ids = list(collection.images.order_by("pk").values_list("pk", flat=True))
        tasks = StudyTask.objects.bulk_create(
            (
                StudyTask(study=created, annotator=annotator, image_id=pk)
                for annotator in annotators
                for pk in image_ids
            ),
            batch_size=5_000,
        )
        annotations = Annotation.objects.bulk_create(
            (
                Annotation(
                    study=created,
                    image_id=task.image_id,
                    annotator=task.annotator,
                    task=task,
                    start_time=EPOCH,
                )
                for task in tasks
                if rng.random() < annotated_fraction
            ),
            batch_size=5_000,
        )
        Response.objects.bulk_create(
            (
                Response(annotation=annotation, question=question, choice=rng.choice(choices))
                for annotation in annotations
                for question, choices in questions
            ),
            batch_size=5_000,
        )

    study(PUBLIC_STUDY, collections["small"], annotators, public=True, annotated_fraction=0.5)
    study(PRIVATE_STUDY, collections["misc-1"], annotators[:3], public=False, annotated_fraction=0)
