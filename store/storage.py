import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivatePaymentProofStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(location=None, base_url=None)

    @property
    def location(self):
        return os.fspath(settings.PAYMENT_PROOF_ROOT)

    @property
    def base_url(self):
        return None
