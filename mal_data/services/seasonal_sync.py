from datetime import datetime, timezone as datetime_timezone

from django.utils import timezone

from mal_data.models import SeasonalAnime
from mal_data.services.anilist_client import AniListClient


def timestamp_to_datetime(timestamp):
    if not timestamp:
        return None

    return datetime.fromtimestamp(timestamp, tz=datetime_timezone.utc)


def sync_seasonal_anime(season, season_year):
    client = AniListClient()

    page = 1
    created_count = 0
    updated_count = 0
    synced_items = []

    while True:
        response = client.fetch_seasonal_anime(
            season=season,
            season_year=season_year,
            page=page,
            per_page=50,
        )

        page_info = response["pageInfo"]
        media_items = response["media"]

        for item in media_items:
            title = item.get("title") or {}
            cover_image = item.get("coverImage") or {}
            next_airing = item.get("nextAiringEpisode") or {}
            studios_data = item.get("studios") or {}
            studio_nodes = studios_data.get("nodes") or []

            studios = [
                studio.get("name")
                for studio in studio_nodes
                if studio.get("name")
            ]

            seasonal_anime, created = SeasonalAnime.objects.update_or_create(
                anilist_id=item["id"],
                defaults={
                    "mal_id": item.get("idMal"),
                    "title_romaji": title.get("romaji") or "",
                    "title_english": title.get("english") or "",
                    "title_native": title.get("native") or "",
                    "cover_image_url": cover_image.get("large") or cover_image.get("medium") or "",
                    "season": item.get("season") or season.upper(),
                    "season_year": item.get("seasonYear") or season_year,
                    "format": item.get("format") or "",
                    "status": item.get("status") or "",
                    "episodes": item.get("episodes") or 0,
                    "next_airing_episode": next_airing.get("episode"),
                    "next_airing_at": timestamp_to_datetime(next_airing.get("airingAt")),
                    "genres": item.get("genres") or [],
                    "studios": studios,
                    "external_links": item.get("externalLinks") or [],
                    "raw_data": item,
                    "last_synced_at": timezone.now(),
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

            synced_items.append(seasonal_anime)

        if not page_info.get("hasNextPage"):
            break

        page += 1

    return {
        "season": season.upper(),
        "season_year": season_year,
        "created_count": created_count,
        "updated_count": updated_count,
        "total_count": len(synced_items),
    }