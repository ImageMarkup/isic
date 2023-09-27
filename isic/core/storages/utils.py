from uuid import uuid4


def generate_upload_to(instance, filename) -> str:
    return str(uuid4())
