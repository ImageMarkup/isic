"""Anonymize a production database dump for use in development/staging environments.

Replaces real data (names, emails, institutional info, private IDs) with deterministic
fake data, clears sensitive tables (sessions, OAuth tokens), and wipes unstructured
metadata. All users are given the password "password".
"""

import hashlib
import logging
import random
import secrets

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.db import connection, transaction
import djclick as click
from faker import Faker
from oauth2_provider.models import AccessToken, RefreshToken

from isic.core.models import IsicOAuthApplication
from isic.core.models.collection import Collection
from isic.ingest.models import (
    Accession,
    Cohort,
    Contributor,
    Lesion,
    MetadataFile,
    MetadataVersion,
    Patient,
    RcmCase,
    ZipUpload,
)
from isic.ingest.models.unstructured_metadata import UnstructuredMetadata
from isic.login.models import HASH_ID_ALPHABET, Profile
from isic.stats.models import ImageDownload
from isic.studies.models import Study

logger = logging.getLogger(__name__)


def _deterministic_hash(salt: str, value: str, prefix: str = "") -> str:
    combined = f"{salt}:{prefix}:{value}"
    return hashlib.sha256(combined.encode()).hexdigest()


def _seeded_faker(faker: Faker, salt: str, value: str, prefix: str) -> Faker:
    seed = int(_deterministic_hash(salt, value, prefix)[:8], 16)
    faker.seed_instance(seed)
    return faker


def anonymize_name(faker: Faker, salt: str, name: str, name_type: str, *, cache: dict) -> str:
    cache_key = f"{name_type}:{name}"
    if cache_key in cache:
        return cache[cache_key]

    _seeded_faker(faker, salt, name, name_type)
    result = faker.first_name() if name_type == "first" else faker.last_name()

    cache[cache_key] = result
    return result


def anonymize_email(salt: str, email: str, *, cache: dict) -> str:
    if email in cache:
        return cache[email]

    hash_val = _deterministic_hash(salt, email, "email")

    result = f"user{hash_val[:8]}@example.test"

    cache[email] = result
    return result


def anonymize_username(salt: str, username: str) -> str:
    hash_val = _deterministic_hash(salt, username, "username")
    return f"user_{hash_val[:12]}"


def anonymize_institution(faker: Faker, salt: str, name: str) -> str:
    _seeded_faker(faker, salt, name, "institution")
    hash_val = _deterministic_hash(salt, name, "institution")[:6]
    return f"{faker.company()} - {hash_val}"


def anonymize_url(faker: Faker, salt: str, url: str) -> str:
    if not url:
        return ""
    _seeded_faker(faker, salt, url, "url")
    return faker.url()


def anonymize_private_id(salt: str, private_id: str, id_type: str, *, cache: dict) -> str:
    cache_key = f"{id_type}:{private_id}"
    if cache_key in cache:
        return cache[cache_key]

    hash_val = _deterministic_hash(salt, private_id, id_type)
    result = f"anon_{id_type}_{hash_val[:12]}"

    cache[cache_key] = result
    return result


def anonymize_client_secret() -> str:
    return secrets.token_hex(32)


def anonymize_hash_id(salt: str, hash_id: str, *, seen: set) -> str:
    for attempt in range(100):
        hash_val = _deterministic_hash(salt, f"{hash_id}:{attempt}", "hash_id")
        seed = int(hash_val[:16], 16)
        # Deterministic PRNG is intentional here; secrets.SystemRandom can't be seeded.
        rng = random.Random(seed)  # noqa: S311
        result = "".join(rng.choice(HASH_ID_ALPHABET) for _ in range(5))
        if result not in seen:
            seen.add(result)
            return result

    raise RuntimeError(f"Failed to generate unique hash_id after 100 attempts: {hash_id}")


def _batch_anonymize(queryset, fields, transform, *, label, dry_run, batch_size):  # noqa: PLR0913
    model_class = queryset.model
    total = queryset.count()
    objects_to_update = []

    if dry_run:
        label = f"[DRY RUN] {label}"

    def _flush():
        if objects_to_update and not dry_run:
            model_class.objects.bulk_update(objects_to_update, fields, batch_size=batch_size)

    with click.progressbar(
        queryset.iterator(), length=total, label=label, show_eta=True, show_percent=True
    ) as bar:
        for obj in bar:
            transform(obj)
            objects_to_update.append(obj)

            if len(objects_to_update) >= batch_size:
                _flush()
                objects_to_update = []

    _flush()

    return total


def _anonymize_users(faker, salt, *, dry_run, batch_size):
    password_hash = make_password("password")
    names_cache = {}
    emails_cache = {}

    def transform(user):
        user.username = anonymize_username(salt, user.username)
        user.first_name = anonymize_name(
            faker, salt, user.first_name or "First", "first", cache=names_cache
        )
        user.last_name = anonymize_name(
            faker, salt, user.last_name or "Last", "last", cache=names_cache
        )
        user.email = anonymize_email(salt, user.email, cache=emails_cache)
        user.password = password_hash

    count = _batch_anonymize(
        User.objects.only("pk", "username", "first_name", "last_name", "email", "password"),
        ["username", "first_name", "last_name", "email", "password"],
        transform,
        label="Anonymizing Users",
        dry_run=dry_run,
        batch_size=batch_size,
    )

    return count, emails_cache


def _anonymize_email_addresses(salt, emails_cache, *, dry_run, batch_size):
    def transform(addr):
        addr.email = anonymize_email(salt, addr.email, cache=emails_cache)

    return _batch_anonymize(
        EmailAddress.objects.only("pk", "email"),
        ["email"],
        transform,
        label="Anonymizing Email Addresses",
        dry_run=dry_run,
        batch_size=batch_size,
    )


def _anonymize_profiles(salt, *, dry_run, batch_size):
    seen_hash_ids = set(Profile.objects.values_list("hash_id", flat=True))

    def transform(profile):
        profile.hash_id = anonymize_hash_id(salt, profile.hash_id, seen=seen_hash_ids)

    return _batch_anonymize(
        Profile.objects.only("pk", "hash_id"),
        ["hash_id"],
        transform,
        label="Anonymizing Profiles",
        dry_run=dry_run,
        batch_size=batch_size,
    )


def _anonymize_contributors(faker, salt, *, dry_run, batch_size):
    def transform(contributor):
        contributor.institution_name = anonymize_institution(
            faker, salt, contributor.institution_name
        )
        contributor.institution_url = anonymize_url(faker, salt, contributor.institution_url)
        _seeded_faker(faker, salt, contributor.legal_contact_info or "", "legal_contact_info")
        contributor.legal_contact_info = faker.text(max_nb_chars=200)
        hash_val = _deterministic_hash(salt, contributor.default_attribution or "", "attribution")[
            :8
        ]
        contributor.default_attribution = f"Anonymous Institution {hash_val}"

    return _batch_anonymize(
        Contributor.objects.only(
            "pk", "institution_name", "institution_url", "legal_contact_info", "default_attribution"
        ),
        ["institution_name", "institution_url", "legal_contact_info", "default_attribution"],
        transform,
        label="Anonymizing Contributors",
        dry_run=dry_run,
        batch_size=batch_size,
    )


def _anonymize_private_ids(salt, *, dry_run, batch_size):
    models_to_process = [
        (Patient, "private_patient_id", "patient"),
        (Lesion, "private_lesion_id", "lesion"),
        (RcmCase, "private_rcm_case_id", "rcm_case"),
    ]

    counts = {}
    for model_class, field_name, id_type in models_to_process:
        cache = {}

        def transform(obj, _field=field_name, _type=id_type, _cache=cache):
            current_value = getattr(obj, _field)
            setattr(obj, _field, anonymize_private_id(salt, current_value, _type, cache=_cache))

        counts[id_type + "s"] = _batch_anonymize(
            model_class.objects.only("pk", field_name),
            [field_name],
            transform,
            label=f"Anonymizing {model_class.__name__}s",
            dry_run=dry_run,
            batch_size=batch_size,
        )

    return counts


def _anonymize_accessions(salt, *, dry_run):
    count = Accession.objects.count()
    click.echo(f"{'[DRY RUN] ' if dry_run else ''}Anonymizing {count} Accessions...")
    if not dry_run:
        table = Accession._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE {table}
                SET
                    original_blob_name = CASE
                        WHEN original_blob_name = '' THEN ''
                        WHEN original_blob_name LIKE '%%.%%' THEN
                            'anon_image_'
                            || substr(md5(%s || ':blob:' || original_blob_name), 1, 16)
                            || '.'
                            || reverse(split_part(reverse(original_blob_name), '.', 1))
                        ELSE
                            'anon_image_'
                            || substr(md5(%s || ':blob:' || original_blob_name), 1, 16)
                    END,
                    attribution = CASE
                        WHEN attribution = '' THEN ''
                        ELSE
                            'Anonymous Institution '
                            || substr(md5(%s || ':attribution:' || attribution), 1, 8)
                    END
                """,  # noqa: S608
                [salt, salt, salt],
            )
    return count


def _anonymize_collections(faker, salt, *, dry_run, batch_size):
    def transform(collection):
        hash_val = _deterministic_hash(salt, collection.name, "collection_name")[:8]
        collection.name = f"Collection {hash_val}"

        if collection.description:
            _seeded_faker(faker, salt, collection.description, "collection_description")
            collection.description = faker.text(max_nb_chars=200)

    return _batch_anonymize(
        Collection.objects.private().only("pk", "name", "description"),
        ["name", "description"],
        transform,
        label="Anonymizing Private Collections",
        dry_run=dry_run,
        batch_size=batch_size,
    )


def _anonymize_cohorts(faker, salt, *, dry_run, batch_size):
    def transform(cohort):
        hash_val = _deterministic_hash(salt, cohort.name, "cohort_name")[:8]
        cohort.name = f"Cohort {hash_val}"

        _seeded_faker(faker, salt, cohort.description or "", "cohort_description")
        cohort.description = faker.text(max_nb_chars=200)

        hash_val = _deterministic_hash(salt, cohort.default_attribution or "", "attribution")[:8]
        cohort.default_attribution = f"Anonymous Institution {hash_val}"

    return _batch_anonymize(
        Cohort.objects.only("pk", "name", "description", "default_attribution"),
        ["name", "description", "default_attribution"],
        transform,
        label="Anonymizing Cohorts",
        dry_run=dry_run,
        batch_size=batch_size,
    )


def _anonymize_studies(faker, salt, *, dry_run, batch_size):
    def transform(study):
        hash_val = _deterministic_hash(salt, study.name, "study_name")[:8]
        study.name = f"Study {hash_val}"

        if study.description:
            _seeded_faker(faker, salt, study.description, "study_description")
            study.description = faker.text(max_nb_chars=200)

        hash_val = _deterministic_hash(salt, study.attribution, "attribution")[:8]
        study.attribution = f"Anonymous Institution {hash_val}"

    return _batch_anonymize(
        Study.objects.only("pk", "name", "description", "attribution"),
        ["name", "description", "attribution"],
        transform,
        label="Anonymizing Studies",
        dry_run=dry_run,
        batch_size=batch_size,
    )


def _anonymize_upload_blob_names(salt, *, dry_run):
    counts = {}
    for model_class, label in [(ZipUpload, "ZipUpload"), (MetadataFile, "MetadataFile")]:
        table = model_class._meta.db_table
        count = model_class.objects.count()
        click.echo(f"{'[DRY RUN] ' if dry_run else ''}Anonymizing {count} {label} blob names...")
        if not dry_run:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {table}
                    SET blob_name = CASE
                        WHEN blob_name = '' THEN ''
                        WHEN blob_name LIKE '%%.%%' THEN
                            'anon_upload_'
                            || substr(md5(%s || ':blob_name:' || blob_name), 1, 16)
                            || '.'
                            || reverse(split_part(reverse(blob_name), '.', 1))
                        ELSE
                            'anon_upload_'
                            || substr(md5(%s || ':blob_name:' || blob_name), 1, 16)
                    END
                    """,  # noqa: S608
                    [salt, salt],
                )
        counts[label.lower() + "s"] = count

    return counts


def _anonymize_unstructured_metadata(*, dry_run):
    count = UnstructuredMetadata.objects.count()
    click.echo(f"{'[DRY RUN] ' if dry_run else ''}Clearing {count} UnstructuredMetadata records...")
    if not dry_run:
        UnstructuredMetadata.objects.update(value={})
    return count


def _anonymize_metadata_versions(*, dry_run):
    count = MetadataVersion.objects.count()
    click.echo(f"{'[DRY RUN] ' if dry_run else ''}Clearing {count} MetadataVersion records...")
    if not dry_run:
        MetadataVersion.objects.update(unstructured_metadata={}, patient={}, lesion={}, rcm_case={})
    return count


def _anonymize_oauth_applications(faker, salt, *, dry_run, batch_size):
    def transform(app):
        _seeded_faker(faker, salt, app.name, "oauth_app_name")
        app.name = f"App {faker.company()}"
        app.client_id = secrets.token_hex(20)
        app.client_secret = anonymize_client_secret()

    return _batch_anonymize(
        IsicOAuthApplication.objects.only("pk", "name", "client_id", "client_secret"),
        ["name", "client_id", "client_secret"],
        transform,
        label="Anonymizing OAuth Applications",
        dry_run=dry_run,
        batch_size=batch_size,
    )


def _clear_sensitive_tables(*, dry_run):
    prefix = "[DRY RUN] " if dry_run else ""
    model_tables = [
        (Session, "Django Sessions", "sessions"),
        (AccessToken, "OAuth Access Tokens", "access_tokens"),
        (RefreshToken, "OAuth Refresh Tokens", "refresh_tokens"),
        (SocialToken, "Social Auth Tokens", "social_tokens"),
        (SocialAccount, "Social Accounts", "social_accounts"),
        (ImageDownload, "Image Downloads", "image_downloads"),
    ]

    counts = {}
    for model_class, label, stats_key in model_tables:
        count = model_class.objects.count()
        if count > 0:
            click.echo(f"{prefix}Clearing {count} {label}...")
            if not dry_run:
                model_class.objects.all().delete()
            counts[stats_key] = count
        else:
            click.echo(f"No {label} to clear")
            counts[stats_key] = 0

    return counts


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Run without making changes to preview what would be anonymized",
)
@click.option(
    "--batch-size",
    type=int,
    default=1000,
    help="Number of records to process in each batch",
)
def anonymize_database(dry_run: bool, batch_size: int):  # noqa: FBT001
    salt = secrets.token_hex(32)
    faker = Faker()
    faker.seed_instance(int(hashlib.sha256(salt.encode()).hexdigest()[:8], 16))

    stats = {}

    click.echo(f"Starting database anonymization (dry_run={dry_run})...")

    if dry_run:
        click.echo("DRY RUN MODE - No changes will be made to the database")

    try:
        with transaction.atomic():
            stats["users"], emails_cache = _anonymize_users(
                faker, salt, dry_run=dry_run, batch_size=batch_size
            )
            stats["email_addresses"] = _anonymize_email_addresses(
                salt, emails_cache, dry_run=dry_run, batch_size=batch_size
            )
            stats["profiles"] = _anonymize_profiles(salt, dry_run=dry_run, batch_size=batch_size)
            stats["contributors"] = _anonymize_contributors(
                faker, salt, dry_run=dry_run, batch_size=batch_size
            )
            stats.update(_anonymize_private_ids(salt, dry_run=dry_run, batch_size=batch_size))
            stats["accessions"] = _anonymize_accessions(salt, dry_run=dry_run)
            stats["private_collections"] = _anonymize_collections(
                faker, salt, dry_run=dry_run, batch_size=batch_size
            )
            stats["cohorts"] = _anonymize_cohorts(
                faker, salt, dry_run=dry_run, batch_size=batch_size
            )
            stats["studies"] = _anonymize_studies(
                faker, salt, dry_run=dry_run, batch_size=batch_size
            )
            stats.update(_anonymize_upload_blob_names(salt, dry_run=dry_run))
            stats["metadata_records"] = _anonymize_unstructured_metadata(dry_run=dry_run)
            stats["metadata_versions"] = _anonymize_metadata_versions(dry_run=dry_run)
            stats["oauth_apps"] = _anonymize_oauth_applications(
                faker, salt, dry_run=dry_run, batch_size=batch_size
            )
            stats.update(_clear_sensitive_tables(dry_run=dry_run))

            if dry_run:
                click.echo("Rolling back transaction (dry run)")
                transaction.set_rollback(True)

    except Exception:
        logger.exception("Anonymization failed")
        raise

    if dry_run:
        click.echo("Dry run completed - no changes were made.")
    else:
        click.echo("Database anonymization completed successfully!")
    click.echo("Anonymization Statistics:")
    for model, count in stats.items():
        click.echo(f"  {model}: {count} records processed")
