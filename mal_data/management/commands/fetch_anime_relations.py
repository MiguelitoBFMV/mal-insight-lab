import json
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from mal_data.models import AnimeEntry, AnimeRelation, MangaEntry
from mal_data.services.mal_client import MyAnimeListClient


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

        self.stdout.write(self.style.WARNING(f"Importando relaciones para anime MAL ID: {anime_id}"))

        client = MyAnimeListClient()
        data = client.fetch_anime_details(anime_id)

        self.save_raw_json(anime_id, data)

        source_mal_id = data.get("id")
        source_title = data.get("title") or ""

        source_anime = AnimeEntry.objects.filter(mal_id=source_mal_id).first()

        related_anime = data.get("related_anime", [])
        related_manga = data.get("related_manga", [])

        anime_created, anime_updated = self.save_relations(
            source_anime=source_anime,
            source_mal_id=source_mal_id,
            source_title=source_title,
            items=related_anime,
            relation_source_type="anime",
        )

        manga_created, manga_updated = self.save_relations(
            source_anime=source_anime,
            source_mal_id=source_mal_id,
            source_title=source_title,
            items=related_manga,
            relation_source_type="manga",
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Relaciones importadas"))
        self.stdout.write(f"Anime base: {source_title} ({source_mal_id})")
        self.stdout.write(f"Related anime: {len(related_anime)}")
        self.stdout.write(f"Related manga: {len(related_manga)}")
        self.stdout.write(f"Anime creados: {anime_created} | Anime actualizados: {anime_updated}")
        self.stdout.write(f"Manga creados: {manga_created} | Manga actualizados: {manga_updated}")

    def save_raw_json(self, anime_id, data):
        raw_dir = settings.BASE_DIR / "data" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = raw_dir / f"anime_relations_{anime_id}_{timestamp}.json"

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

        self.stdout.write(f"JSON crudo guardado en: {output_file}")

    def save_relations(
        self,
        source_anime,
        source_mal_id,
        source_title,
        items,
        relation_source_type,
    ):
        created_count = 0
        updated_count = 0

        for item in items:
            node = item.get("node", {})
            main_picture = node.get("main_picture") or {}

            target_mal_id = node.get("id")
            target_title = node.get("title") or ""

            if target_mal_id is None:
                continue

            target_local_list_status = self.get_target_local_status(
                target_mal_id=target_mal_id,
                relation_source_type=relation_source_type,
            )

            defaults = {
                "source_anime": source_anime,
                "source_title": source_title,
                "target_title": target_title,
                "target_media_type": node.get("media_type"),
                "target_status": node.get("status"),
                "target_picture_url": main_picture.get("large") or main_picture.get("medium"),
                "relation_type_formatted": item.get("relation_type_formatted"),
                "target_local_list_status": target_local_list_status,
                "raw_data": item,
                "last_synced_at": timezone.now(),
            }

            _, created = AnimeRelation.objects.update_or_create(
                source_mal_id=source_mal_id,
                target_mal_id=target_mal_id,
                relation_source_type=relation_source_type,
                relation_type=item.get("relation_type") or "",
                defaults=defaults,
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        return created_count, updated_count

    def get_target_local_status(self, target_mal_id, relation_source_type):
        if relation_source_type == "anime":
            target = AnimeEntry.objects.filter(mal_id=target_mal_id).first()
            return target.list_status if target else ""

        if relation_source_type == "manga":
            target = MangaEntry.objects.filter(mal_id=target_mal_id).first()
            return target.list_status if target else ""

        return ""