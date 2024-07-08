import logging

import bcrypt
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.utils.translation import gettext_noop as _

logger = logging.getLogger(__name__)


class GirderPasswordHasher(BasePasswordHasher):
    algorithm = "bcrypt_girder"

    def verify(self, password: str, encoded: str) -> bool:
        hashed_password = encoded.split("$", 1)[1]
        return bcrypt.checkpw(password.encode(), hashed_password.encode())

    def salt(self):
        return bcrypt.gensalt().decode("utf-8")

    def encode(self, password, salt):
        hashed = bcrypt.hashpw(password.encode(), salt.encode()).decode()
        return f"{self.algorithm}${hashed}"

    def safe_summary(self, encoded: str):
        return {
            _("algorithm"): self.algorithm,
            _("checksum"): mask_hash(encoded),
        }
