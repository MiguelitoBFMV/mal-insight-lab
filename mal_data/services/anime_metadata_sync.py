from django.utils import timezone

from mal_data.models import AnimeMetadata
from mal_data.services.mal_client import MyAnimeListClient


def sync_anime_metadata(mal_id):
    client = MyAnimeListClient()
    data = client.fetch_anime_details(mal_id)

    main_picture = data.get("main_picture") or {}

    alternative_titles = data.get("alternative_titles") or {}
    start_date = data.get("start_date") or None
    end_date = data.get("end_date") or None

    metadata, created = AnimeMetadata.objects.update_or_create(
        mal_id=data["id"],
        defaults={
            "title": data.get("title", ""),
            "title_japanese": alternative_titles.get("ja", ""),
            "title_english": alternative_titles.get("en", ""),
            "main_picture_url": main_picture.get("large") or main_picture.get("medium") or "",
            "media_type": data.get("media_type", ""),
            "airing_status": data.get("status", ""),
            "num_episodes": data.get("num_episodes") or 0,
            "start_date": start_date,
            "end_date": end_date,
            "raw_data": data,
            "last_synced_at": timezone.now(),
        },
    )

    return metadata, created