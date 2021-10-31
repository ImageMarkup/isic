import logging

from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.utils.translation import gettext_noop as _
from passlib.hash import bcrypt

logger = logging.getLogger(__name__)


class GirderPasswordHasher(BasePasswordHasher):
    algorithm = 'bcrypt_girder'

    def verify(self, password: str, encoded: str) -> bool:
        return bcrypt.verify(password, encoded.split('$', 1)[1])

    def salt(self):
        return bcrypt._generate_salt()

    def encode(self, password, salt):
        hashed = bcrypt.using(salt=salt).hash(password)
        return f'{self.algorithm}${hashed}'

    def safe_summary(self, encoded: str):
        return {
            _('algorithm'): self.algorithm,
            _('checksum'): mask_hash(encoded),
        }
