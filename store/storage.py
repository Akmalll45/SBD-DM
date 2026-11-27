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
            # MediaCloudinaryStorage mendukung semua tipe file (image/pdf/dll)
            # RawMediaCloudinaryStorage hanya untuk non-image; gambar JPG/PNG
            # akan ditolak Cloudinary jika dikirim sebagai resource_type=raw.
            from cloudinary_storage.storage import MediaCloudinaryStorage
            return MediaCloudinaryStorage()
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


@deconstructible
class SablonRosterStorage(Storage):
    """
    Menyimpan file daftar nama sablon (JPG/PNG/DOC/DOCX/XLS/XLSX):
    - Saat CLOUDINARY_URL aktif: gambar via MediaCloudinaryStorage,
      dokumen (doc/docx/xls/xlsx) via RawMediaCloudinaryStorage.
    - Saat development lokal: FileSystemStorage ke MEDIA_ROOT.
    """

    _IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}

    def _backend(self, name=''):
        if getattr(settings, 'CLOUDINARY_URL', ''):
            ext = name.rpartition('.')[2].lower() if '.' in name else ''
            if ext and ext not in self._IMAGE_EXTENSIONS:
                from cloudinary_storage.storage import RawMediaCloudinaryStorage
                return RawMediaCloudinaryStorage()
            from cloudinary_storage.storage import MediaCloudinaryStorage
            return MediaCloudinaryStorage()
        return FileSystemStorage(
            location=os.fspath(settings.MEDIA_ROOT),
            base_url=settings.MEDIA_URL,
        )

    def _open(self, name, mode='rb'):
        return self._backend(name)._open(name, mode=mode)

    def _save(self, name, content):
        return self._backend(name)._save(name, content)

    def delete(self, name):
        return self._backend(name).delete(name)

    def exists(self, name):
        return self._backend(name).exists(name)

    def size(self, name):
        return self._backend(name).size(name)

    def url(self, name):
        return self._backend(name).url(name)

    def get_available_name(self, name, max_length=None):
        return self._backend(name).get_available_name(name, max_length=max_length)
