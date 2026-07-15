import json
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from mal_data.models import AnimeEntry, AnimeSyncEvent
from mal_data.services.mal_client import MyAnimeListClient


VALID_ANIME_STATUSES = [
    "watching",
    "completed",
    "on_hold",
    "dropped",
    "plan_to_watch",
]


def sync_anime_status(status, save_raw=True):
    if status not in VALID_ANIME_STATUSES:
        raise ValueError(f"Estado de anime inválido: {status}")

    client = MyAnimeListClient()

    all_entries = []

    for page_data in client.fetch_all_anime_by_status(status):
        entries = page_data.get("entries", [])
        all_entries.extend(entries)

    if save_raw:
        save_raw_json(status, all_entries)

    created_count = 0
    updated_count = 0

    for item in all_entries:
        _, created = upsert_anime_entry(item)

        if created:
            created_count += 1
        else:
            updated_count += 1

    return {
        "status": status,
        "total": len(all_entries),
        "created": created_count,
        "updated": updated_count,
    }


def sync_all_anime_statuses(save_raw=True):
    results = []

    for status in VALID_ANIME_STATUSES:
        result = sync_anime_status(status, save_raw=save_raw)
        results.append(result)

    return results


def save_raw_json(status, entries):
    raw_dir = settings.BASE_DIR / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = raw_dir / f"anime_{status}_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(entries, file, indent=2, ensure_ascii=False)

    return output_file


def upsert_anime_entry(item):
    node = item.get("node", {})
    list_status = item.get("list_status", {})
    main_picture = node.get("main_picture") or {}
    alternative_titles = node.get("alternative_titles") or {}

    mal_id = node.get("id")

    if mal_id is None:
        raise ValueError("Anime sin MAL ID en respuesta de API.")

    previous = AnimeEntry.objects.filter(mal_id=mal_id).first()

    defaults = {
        "title": node.get("title") or "",
        "title_japanese": alternative_titles.get("ja"),
        "title_english": alternative_titles.get("en"),
        "main_picture_url": main_picture.get("large") or main_picture.get("medium"),
        "media_type": node.get("media_type"),
        "airing_status": node.get("status"),
        "num_episodes": node.get("num_episodes") or 0,
        "start_date": parse_date(node.get("start_date")),
        "end_date": parse_date(node.get("end_date")),
        "list_status": list_status.get("status") or "",
        "score": list_status.get("score") or 0,
        "num_episodes_watched": list_status.get("num_episodes_watched") or 0,
        "is_rewatching": list_status.get("is_rewatching") or False,
        "updated_at_mal": parse_datetime(list_status.get("updated_at")),
        "raw_data": item,
        "last_synced_at": timezone.now(),
    }

    anime, created = AnimeEntry.objects.update_or_create(
        mal_id=mal_id,
        defaults=defaults,
    )

    create_sync_events(
        anime=anime,
        previous=previous,
        created=created,
    )

    return anime, created


def create_sync_events(anime, previous, created):
    if created:
        AnimeSyncEvent.objects.create(
            anime=anime,
            mal_id=anime.mal_id,
            title_snapshot=anime.display_title,
            event_type="created",
            old_value="not_in_local_db",
            new_value=anime.list_status,
        )
        return

    if previous is None:
        return

    if previous.list_status != anime.list_status:
        AnimeSyncEvent.objects.create(
            anime=anime,
            mal_id=anime.mal_id,
            title_snapshot=anime.display_title,
            event_type="status_changed",
            old_value=previous.personal_status_label,
            new_value=anime.personal_status_label,
        )

    if previous.num_episodes_watched != anime.num_episodes_watched:
        AnimeSyncEvent.objects.create(
            anime=anime,
            mal_id=anime.mal_id,
            title_snapshot=anime.display_title,
            event_type="episode_changed",
            old_value=f"EP. {previous.num_episodes_watched}",
            new_value=f"EP. {anime.num_episodes_watched}",
        )

    if previous.score != anime.score:
        AnimeSyncEvent.objects.create(
            anime=anime,
            mal_id=anime.mal_id,
            title_snapshot=anime.display_title,
            event_type="score_changed",
            old_value=f"Score {previous.score}",
            new_value=f"Score {anime.score}",
        )

def parse_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None