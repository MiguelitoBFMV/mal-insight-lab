from django.core.management.base import BaseCommand

from mal_data.services.anime_list_sync import (
    VALID_ANIME_STATUSES,
    sync_anime_status,
)


class Command(BaseCommand):
    help = "Importa anime desde MyAnimeList según estado de la lista."

    def add_arguments(self, parser):
        parser.add_argument(
            "status",
            choices=VALID_ANIME_STATUSES,
            help="Estado de la lista de anime en MAL.",
        )

    def handle(self, *args, **options):
        status = options["status"]

        self.stdout.write(
            self.style.WARNING(
                f"Importando anime con estado: {status}"
            )
        )

        result = sync_anime_status(status)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Importación completada"))
        self.stdout.write(f"Estado: {result['status']}")
        self.stdout.write(f"Total: {result['total']}")
        self.stdout.write(f"Creados: {result['created']}")
        self.stdout.write(f"Actualizados: {result['updated']}")