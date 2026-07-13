import json
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from mal_data.models import AnimeEntry
from mal_data.services.mal_client import MyAnimeListClient


class Command(BaseCommand):
    help = "Importa animes desde MyAnimeList por status."

    VALID_STATUSES = {
        "watching",
        "completed",
        "on_hold",
        "dropped",
        "plan_to_watch",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "status",
            type=str,
            help="Estado de anime en MAL: watching, completed, on_hold, dropped, plan_to_watch",
        )

    def handle(self, *args, **options):
        status = options["status"]

        if status not in self.VALID_STATUSES:
            self.stderr.write(
                self.style.ERROR(
                    f"Status inválido: {status}. Usa uno de: {', '.join(sorted(self.VALID_STATUSES))}"
                )
            )
            return

        self.stdout.write(self.style.WARNING(f"Importando animes con status: {status}"))

        client = MyAnimeListClient()
        all_entries = []

        for page_result in client.fetch_all_anime_by_status(status):
            page = page_result["page"]
            entries = page_result["entries"]
            total_accumulated = page_result["total_accumulated"]

            all_entries.extend(entries)

            self.stdout.write(
                f"Página {page}: {len(entries)} entradas | Total acumulado: {total_accumulated}"
            )

        self.save_raw_json(status, all_entries)

        created_count = 0
        updated_count = 0

        for item in all_entries:
            _, created = self.upsert_anime_entry(item)

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Importación finalizada"))
        self.stdout.write(f"Total recibidos desde MAL: {len(all_entries)}")
        self.stdout.write(f"Creados: {created_count}")
        self.stdout.write(f"Actualizados: {updated_count}")

    def save_raw_json(self, status, entries):
        raw_dir = settings.BASE_DIR / "data" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = raw_dir / f"anime_{status}_{timestamp}.json"

        payload = {
            "status_filter": status,
            "total": len(entries),
            "data": entries,
        }

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

        self.stdout.write(f"JSON crudo guardado en: {output_file}")

    def upsert_anime_entry(self, item):
        node = item.get("node", {})
        list_status = item.get("list_status", {})
        main_picture = node.get("main_picture") or {}

        mal_id = node.get("id")

        if mal_id is None:
            raise ValueError(f"Entrada sin MAL ID: {item}")

        updated_at_raw = list_status.get("updated_at")
        updated_at_mal = parse_datetime(updated_at_raw) if updated_at_raw else None

        defaults = {
            "title": node.get("title") or "",
            "main_picture_url": main_picture.get("large") or main_picture.get("medium"),
            "media_type": node.get("media_type"),
            "airing_status": node.get("status"),
            "num_episodes": node.get("num_episodes") or 0,
            "start_date": parse_date(node.get("start_date")) if node.get("start_date") else None,
            "end_date": parse_date(node.get("end_date")) if node.get("end_date") else None,
            "list_status": list_status.get("status") or "",
            "score": list_status.get("score") or 0,
            "num_episodes_watched": list_status.get("num_episodes_watched") or 0,
            "is_rewatching": list_status.get("is_rewatching") or False,
            "updated_at_mal": updated_at_mal,
            "raw_data": item,
            "last_synced_at": timezone.now(),
        }

        return AnimeEntry.objects.update_or_create(
            mal_id=mal_id,
            defaults=defaults,
        )