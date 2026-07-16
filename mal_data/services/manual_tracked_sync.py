from django.utils import timezone

from mal_data.models import AnimeEntry, ManualTrackedAnime
from mal_data.services.anime_list_sync import parse_date
from mal_data.services.mal_client import MyAnimeListClient


def sync_manual_tracked_anime_entry(tracked_entry):
    client = MyAnimeListClient()
    details = client.fetch_anime_details(tracked_entry.mal_id)

    main_picture = details.get("main_picture") or {}
    alternative_titles = details.get("alternative_titles") or {}

    anime, created = AnimeEntry.objects.update_or_create(
        mal_id=tracked_entry.mal_id,
        defaults={
            "title": details.get("title") or tracked_entry.title_snapshot or "",
            "title_japanese": alternative_titles.get("ja"),
            "title_english": alternative_titles.get("en"),
            "main_picture_url": main_picture.get("large") or main_picture.get("medium"),
            "media_type": details.get("media_type"),
            "airing_status": details.get("status"),
            "num_episodes": details.get("num_episodes") or 0,
            "start_date": parse_date(details.get("start_date")),
            "end_date": parse_date(details.get("end_date")),
            "list_status": tracked_entry.status,
            "score": tracked_entry.score,
            "num_episodes_watched": tracked_entry.episodes_watched,
            "is_rewatching": tracked_entry.is_rewatching,
            "updated_at_mal": timezone.now(),
            "raw_data": {
                "source": "manual_tracked_sync",
                "details": details,
                "manual_status": {
                    "status": tracked_entry.status,
                    "episodes_watched": tracked_entry.episodes_watched,
                    "score": tracked_entry.score,
                    "is_rewatching": tracked_entry.is_rewatching,
                },
            },
            "last_synced_at": timezone.now(),
        },
    )

    if not tracked_entry.title_snapshot:
        tracked_entry.title_snapshot = anime.display_title
        tracked_entry.save(update_fields=["title_snapshot", "updated_at"])

    return anime, created


def sync_manual_tracked_anime_entries():
    tracked_entries = ManualTrackedAnime.objects.filter(active=True).order_by("title_snapshot", "mal_id")

    results = []

    for tracked_entry in tracked_entries:
        try:
            anime, created = sync_manual_tracked_anime_entry(tracked_entry)

            results.append(
                {
                    "mal_id": tracked_entry.mal_id,
                    "title": anime.display_title,
                    "created": created,
                    "ok": True,
                    "error": None,
                }
            )
        except Exception as error:
            results.append(
                {
                    "mal_id": tracked_entry.mal_id,
                    "title": tracked_entry.title_snapshot or f"MAL ID {tracked_entry.mal_id}",
                    "created": False,
                    "ok": False,
                    "error": str(error),
                }
            )

    return results