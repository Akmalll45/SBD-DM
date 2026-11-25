import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivatePaymentProofStorage(Storage):
    """
    Menyimpan bukti pembayaran ke Cloudinary (raw) saat CLOUDINARY_URL aktif (Vercel/production),
    atau ke filesystem lokal (PAYMENT_PROOF_ROOT) saat development lokal.
    """

    def _backend(self):
        if getattr(settings, 'CLOUDINARY_URL', ''):
            from cloudinary_storage.storage import RawMediaCloudinaryStorage
            return RawMediaCloudinaryStorage()
        return FileSystemStorage(
            location=os.fspath(settings.PAYMENT_PROOF_ROOT),
            base_url=None,
        )

    def _open(self, name, mode='rb'):
        return self._backend()._open(name, mode=mode)

    def _save(self, name, content):
        return self._backend()._save(name, content)

    def delete(self, name):
        return self._backend().delete(name)

    def exists(self, name):
        return self._backend().exists(name)

    def size(self, name):
        return self._backend().size(name)

    def url(self, name):
        return None

    def get_available_name(self, name, max_length=None):
        return self._backend().get_available_name(name, max_length=max_length)
