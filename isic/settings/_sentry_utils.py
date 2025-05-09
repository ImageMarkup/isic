from sentry_sdk._types import SamplingContext


def get_sentry_performance_sample_rate(sampling_context: SamplingContext) -> float:
    """Determine sample rate of sentry performance."""
    from isic.core.tasks import populate_collection_from_search_task
    from isic.ingest.tasks import (
        extract_zip_task,
        publish_cohort_task,
        update_metadata_task,
        validate_metadata_task,
    )
    from isic.studies.tasks import populate_study_tasks_task

    infrequent_tasks = {
        task.name
        for task in [
            extract_zip_task,
            validate_metadata_task,
            update_metadata_task,
            publish_cohort_task,
            populate_collection_from_search_task,
            populate_study_tasks_task,
        ]
    }

    if "wsgi_environ" in sampling_context:
        path: str = sampling_context["wsgi_environ"]["PATH_INFO"]
        if path.startswith(("/staff", "/admin")):
            return 1.0

        # Sample more important endpoints at a higher rate. Note that this can't be done
        # with a decorator on the views because of how django-ninja resolves everything
        # to one view function.
        if any(
            path.startswith(prefix)
            for prefix in (
                "/api/v2/images",
                "/api/v2/quickfind",
                "/api/v2/lesions",
                "/api/v2/zip-download",
            )
        ):
            return 0.20
    elif "celery_job" in sampling_context:
        if sampling_context["celery_job"]["task"] in infrequent_tasks:
            return 1.0

    return 0.05
