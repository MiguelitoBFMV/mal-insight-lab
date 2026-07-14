from django.core.management.base import BaseCommand

from mal_data.services.anime_relations_sync import sync_anime_relations


class Command(BaseCommand):
    help = "Importa relaciones related_anime y related_manga de un anime específico desde MyAnimeList."

    def add_arguments(self, parser):
        parser.add_argument(
            "anime_id",
            type=int,
            help="MAL ID del anime base.",
        )

    def handle(self, *args, **options):
        anime_id = options["anime_id"]

        self.stdout.write(
            self.style.WARNING(
                f"Importando relaciones para anime MAL ID: {anime_id}"
            )
        )

        result = sync_anime_relations(anime_id)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Relaciones importadas"))
        self.stdout.write(
            f"Anime base: {result['source_title']} ({result['source_mal_id']})"
        )
        self.stdout.write(f"Related anime: {result['related_anime_count']}")
        self.stdout.write(f"Related manga: {result['related_manga_count']}")
        self.stdout.write(
            f"Anime creados: {result['anime_created']} | "
            f"Anime actualizados: {result['anime_updated']}"
        )
        self.stdout.write(
            f"Manga creados: {result['manga_created']} | "
            f"Manga actualizados: {result['manga_updated']}"
        )