def string_to_list(value: str, separator=",") -> list:
    """Attempt to parse a string as a list of separated values."""
    split_value = [v.strip() for v in value.strip().split(separator)]
    return list(filter(None, split_value))


def string_to_bool(value: str) -> bool:
    true_values = ("yes", "y", "true", "1")
    false_values = ("no", "n", "false", "0", "")

    normalized_value = value.strip().lower()
    if normalized_value in true_values:
        return True
    if normalized_value in false_values:
        return False

    raise ValueError("Cannot interpret " f"boolean value {value!r}")


def _get_sentry_performance_sample_rate(*args, **kwargs) -> float:
    """
    Determine sample rate of sentry performance.

    Only sample 1% of common requests for performance monitoring, and all staff/admin requests
    since they're relatively low volume but high value. Also sample all infrequent tasks.
    """
    from isic.core.tasks import populate_collection_from_search_task
    from isic.ingest.tasks import (
        extract_zip_task,
        publish_cohort_task,
        update_metadata_task,
        validate_metadata_task,
    )
    from isic.studies.tasks import populate_study_tasks_task

    infrequent_tasks = [
        task.name
        for task in [
            extract_zip_task,
            validate_metadata_task,
            update_metadata_task,
            publish_cohort_task,
            populate_collection_from_search_task,
            populate_study_tasks_task,
        ]
    ]

    if args and "wsgi_environ" in args[0]:
        path: str = args[0]["wsgi_environ"]["PATH_INFO"]
        if path.startswith(("/staff", "/admin")):
            return 1.0
    elif args and "celery_job" in args[0]:
        if args[0]["celery_job"]["task"] in infrequent_tasks:
            return 1.0

    return 0.05
