from django.core.management.base import BaseCommand

from mal_data.services.anime_metadata_sync import sync_anime_metadata


class Command(BaseCommand):
    help = "Sync public anime metadata from MyAnimeList for a given MAL anime ID."

    def add_arguments(self, parser):
        parser.add_argument("mal_id", type=int)

    def handle(self, *args, **options):
        mal_id = options["mal_id"]

        metadata, created = sync_anime_metadata(mal_id)

        action = "Created" if created else "Updated"

        self.stdout.write(
            self.style.SUCCESS(
                f"{action} AnimeMetadata: {metadata.title} "
                f"(MAL ID: {metadata.mal_id})"
            )
        )