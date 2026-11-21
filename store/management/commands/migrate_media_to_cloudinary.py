from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from store.models import Category, Product


class Command(BaseCommand):
    help = "Uploads existing local media files to the configured Django default storage."

    def handle(self, *args, **options):
        if "MediaCloudinaryStorage" not in settings.STORAGES["default"]["BACKEND"]:
            raise CommandError(
                "CLOUDINARY_URL is not configured. Set it before running this command."
            )

        uploaded = 0
        missing = []

        for model in (Category, Product):
            for obj in model.objects.exclude(
                **{"image": ""}
            ):
                field_names = ["image"]
                if model is Product:
                    field_names += ["front_image", "back_image"]

                for field_name in field_names:
                    field = getattr(obj, field_name)
                    if not field:
                        continue

                    local_path = settings.MEDIA_ROOT / field.name
                    if not local_path.is_file():
                        missing.append(str(field.name))
                        continue

                    with local_path.open("rb") as source:
                        saved_name = field.storage.save(field.name, File(source))

                    if saved_name != field.name:
                        setattr(obj, field_name, saved_name)
                        obj.save(update_fields=[field_name])

                    uploaded += 1

        self.stdout.write(
            self.style.SUCCESS(f"Migrated {uploaded} media file(s) to Cloudinary.")
        )
        if missing:
            self.stdout.write(
                self.style.WARNING(
                    "Files not found locally:\n- " + "\n- ".join(sorted(set(missing)))
                )
            )
