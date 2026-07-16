from django.core.management.base import BaseCommand
from django.utils import timezone

from mal_data.models import AnimeEntry, ManualTrackedAnime
from mal_data.services.anilist_airing_sync import sync_airing_data_for_anime
from mal_data.services.mal_client import MyAnimeListClient
from mal_data.services.anime_list_sync import parse_date


VALID_STATUSES = [
    "watching",
    "completed",
    "on_hold",
    "dropped",
    "plan_to_watch",
]


class Command(BaseCommand):
    help = "Rescata/importa manualmente un anime por MAL ID cuando el endpoint de lista no lo devuelve."

    def add_arguments(self, parser):
        parser.add_argument(
            "anime_id",
            type=int,
            help="MAL ID del anime a rescatar.",
        )

        parser.add_argument(
            "--status",
            choices=VALID_STATUSES,
            required=True,
            help="Estado personal local que tendrá el anime.",
        )

        parser.add_argument(
            "--episodes-watched",
            type=int,
            default=0,
            help="Cantidad de episodios vistos.",
        )

        parser.add_argument(
            "--score",
            type=int,
            default=0,
            help="Score personal. Usa 0 si no tiene score.",
        )

        parser.add_argument(
            "--sync-airing",
            action="store_true",
            help="Sincroniza también datos de emisión desde AniList.",
        )

    def handle(self, *args, **options):
        anime_id = options["anime_id"]
        status = options["status"]
        episodes_watched = options["episodes_watched"]
        score = options["score"]
        sync_airing = options["sync_airing"]

        self.stdout.write(
            self.style.WARNING(
                f"Rescatando anime MAL ID: {anime_id}"
            )
        )

        client = MyAnimeListClient()
        details = client.fetch_anime_details(anime_id)

        main_picture = details.get("main_picture") or {}
        alternative_titles = details.get("alternative_titles") or {}

        anime, created = AnimeEntry.objects.update_or_create(
            mal_id=anime_id,
            defaults={
                "title": details.get("title") or "",
                "title_japanese": alternative_titles.get("ja"),
                "title_english": alternative_titles.get("en"),
                "main_picture_url": main_picture.get("large") or main_picture.get("medium"),
                "media_type": details.get("media_type"),
                "airing_status": details.get("status"),
                "num_episodes": details.get("num_episodes") or 0,
                "start_date": parse_date(details.get("start_date")),
                "end_date": parse_date(details.get("end_date")),
                "list_status": status,
                "score": score,
                "num_episodes_watched": episodes_watched,
                "is_rewatching": False,
                "updated_at_mal": timezone.now(),
                "raw_data": {
                    "rescue_source": "manual_rescue",
                    "details": details,
                    "manual_status": {
                        "status": status,
                        "score": score,
                        "num_episodes_watched": episodes_watched,
                    },
                },
                "last_synced_at": timezone.now(),
            },
        )

        ManualTrackedAnime.objects.update_or_create(
            mal_id=anime_id,
            defaults={
                "title_snapshot": anime.display_title,
                "status": status,
                "episodes_watched": episodes_watched,
                "score": score,
                "is_rewatching": False,
                "active": True,
            },
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Anime rescatado correctamente"))
        self.stdout.write(f"Creado: {created}")
        self.stdout.write(f"Anime: {anime.display_title}")
        self.stdout.write(f"MAL ID: {anime.mal_id}")
        self.stdout.write(f"Estado local: {anime.personal_status_label}")
        self.stdout.write(
            f"Progreso: {anime.num_episodes_watched}/{anime.num_episodes or 'TBD'}"
        )
        self.stdout.write(f"Airing status: {anime.airing_status}")

        if sync_airing:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING("Sincronizando datos AniList...")
            )

            try:
                airing_data, airing_created = sync_airing_data_for_anime(anime_id)

                self.stdout.write(self.style.SUCCESS("AniList sincronizado"))
                self.stdout.write(f"AniList ID: {airing_data.anilist_id}")
                self.stdout.write(f"Estimated aired: {airing_data.episodes_aired_estimated}")
                self.stdout.write(f"Next episode: {airing_data.next_airing_episode}")
                self.stdout.write(f"Pending for you: {airing_data.pending_episodes_for_user}")
                self.stdout.write(f"Airing data creado: {airing_created}")
            except Exception as error:
                self.stdout.write(
                    self.style.ERROR(
                        f"No se pudo sincronizar AniList: {error}"
                    )
                )