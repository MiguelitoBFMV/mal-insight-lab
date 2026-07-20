from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from mal_data.models import AnimeEntry, SeasonalAnime
from mal_data.services.anime_list_sync import upsert_anime_entry
from mal_data.services.anilist_airing_sync import (
    sync_airing_data_for_dashboard,
)
from mal_data.services.mal_client import MyAnimeListClient
from mal_data.services.seasonal_sync import (
    sync_seasonal_anime,
    sync_tba_upcoming_anime,
)

def seasonal_board(request):
    valid_seasons = ["ALL", "WINTER", "SPRING", "SUMMER", "FALL"]

    season = request.GET.get("season", "SUMMER").upper()
    if season not in valid_seasons:
        season = "SUMMER"

    year = int(request.GET.get("year", 2026))
    format_filter = request.GET.get("format", "all")
    local_filter = request.GET.get("local", "all")
    sort = request.GET.get("sort", "countdown")

    if season == "ALL":
        seasonal_anime = SeasonalAnime.objects.filter(season_year=year)
    else:
        seasonal_anime = SeasonalAnime.objects.filter(
            season=season,
            season_year=year,
        )

    if format_filter != "all":
        seasonal_anime = seasonal_anime.filter(format=format_filter.upper())

    seasonal_anime = list(seasonal_anime)

    anime_entries_by_mal_id = {
        anime.mal_id: anime
        for anime in AnimeEntry.objects.filter(
            mal_id__in=[
                item.mal_id
                for item in seasonal_anime
                if item.mal_id
            ]
        )
    }

    enriched_items = []

    for item in seasonal_anime:
        local_entry = None

        if item.mal_id:
            local_entry = anime_entries_by_mal_id.get(item.mal_id)

        if local_filter == "in_list" and not local_entry:
            continue

        if local_filter == "not_in_list" and local_entry:
            continue

        if local_filter in {
            "watching",
            "completed",
            "on_hold",
            "dropped",
            "plan_to_watch",
        }:
            if not local_entry or local_entry.list_status != local_filter:
                continue

        enriched_items.append(
            {
                "seasonal": item,
                "local_entry": local_entry,
            }
        )

    def countdown_sort_key(item):
        seasonal = item["seasonal"]
        local_entry = item["local_entry"]

        is_tba_bucket = seasonal.season == "TBA"

        has_next_airing = 0 if seasonal.next_airing_at and not is_tba_bucket else 1

        if seasonal.next_airing_at:
            next_airing_sort = seasonal.next_airing_at
        else:
            next_airing_sort = timezone.datetime.max.replace(
                tzinfo=timezone.get_current_timezone()
            )

        status_priority = {
            "RELEASING": 0,
            "NOT_YET_RELEASED": 1,
            "FINISHED": 2,
            "CANCELLED": 3,
            "HIATUS": 4,
        }.get(seasonal.status, 99)

        local_priority = 1

        if local_entry and local_entry.list_status == "watching":
            local_priority = 0
        elif local_entry and local_entry.list_status == "plan_to_watch":
            local_priority = 1
        elif not local_entry:
            local_priority = 2
        elif local_entry and local_entry.list_status == "completed":
            local_priority = 3
        else:
            local_priority = 4

        return (
            1 if is_tba_bucket else 0,
            has_next_airing,
            next_airing_sort,
            status_priority,
            local_priority,
            seasonal.display_title.lower(),
        )

    if sort == "title":
        enriched_items = sorted(
            enriched_items,
            key=lambda item: item["seasonal"].display_title.lower(),
        )
    else:
        sort = "countdown"
        enriched_items = sorted(enriched_items, key=countdown_sort_key)

    context = {
        "season": season,
        "year": year,
        "format_filter": format_filter,
        "local_filter": local_filter,
        "sort": sort,
        "season_options": valid_seasons,
        "year_options": range(year - 2, year + 3),
        "format_options": [
            "all",
            "TV",
            "TV_SHORT",
            "MOVIE",
            "SPECIAL",
            "OVA",
            "ONA",
            "MUSIC",
        ],
        "local_filter_options": [
            ("all", "All"),
            ("in_list", "In my list"),
            ("not_in_list", "Not in my list"),
            ("watching", "Watching"),
            ("plan_to_watch", "Plan to Watch"),
            ("completed", "Completed"),
        ],
        "sort_options": [
            ("countdown", "Countdown"),
            ("title", "Title A-Z"),
        ],
        "items": enriched_items,
        "total_items": len(enriched_items),
    }

    return render(request, "mal_data/seasonal_board.html", context)

@login_required
@require_POST
def sync_seasonal_board_view(request):

    valid_seasons = ["WINTER", "SPRING", "SUMMER", "FALL"]

    season = request.POST.get("season", "SUMMER").upper()
    year = int(request.POST.get("year", 2026))
    next_url = request.POST.get("next") or "mal_insights:seasonal_board"

    include_tba_bucket = False

    if season == "ALL":
        seasons_to_sync = valid_seasons
        include_tba_bucket = True
    elif season in valid_seasons:
        seasons_to_sync = [season]
    else:
        messages.error(request, "Invalid seasonal board filter.")
        return redirect(next_url)

    try:
        results = [
            sync_seasonal_anime(season_to_sync, year)
            for season_to_sync in seasons_to_sync
        ]

        if include_tba_bucket:
            results.append(sync_tba_upcoming_anime(bucket_year=year))

        created_count = sum(result["created_count"] for result in results)
        updated_count = sum(result["updated_count"] for result in results)
        total_count = sum(result["total_count"] for result in results)

        synced_label = (
            f"ALL {year}"
            if season == "ALL"
            else f"{season} {year}"
        )

        messages.success(
            request,
            (
                f"Seasonal Board synced: {synced_label} · "
                f"Created: {created_count} · "
                f"Updated: {updated_count} · "
                f"Total: {total_count}"
            ),
        )

    except Exception as error:
        messages.error(request, f"Seasonal Board sync failed: {error}")

    return redirect(next_url)

@login_required
@require_POST
def add_seasonal_to_plan_view(request):

    mal_id = request.POST.get("mal_id")
    next_url = request.POST.get("next") or "mal_insights:seasonal_board"

    if not mal_id:
        messages.error(request, "Cannot add seasonal anime without MAL ID.")
        return redirect(next_url)

    try:
        mal_id = int(mal_id)
    except ValueError:
        messages.error(request, "Invalid MAL ID.")
        return redirect(next_url)

    try:
        client = MyAnimeListClient()

        existing_list_status = client.fetch_anime_my_list_status(mal_id)

        if existing_list_status:
            anime_details = client.fetch_anime_details(mal_id)

            anime_payload = {
                "node": anime_details,
                "list_status": {
                    "status": existing_list_status.get("status"),
                    "score": existing_list_status.get("score", 0),
                    "num_episodes_watched": existing_list_status.get(
                        "num_episodes_watched",
                        0,
                    ),
                    "is_rewatching": existing_list_status.get(
                        "is_rewatching",
                        False,
                    ),
                    "updated_at": existing_list_status.get("updated_at"),
                },
            }

            anime, created = upsert_anime_entry(anime_payload)

            messages.info(
                request,
                (
                    "Anime already exists in MyAnimeList. "
                    "Local archive synchronized instead. "
                    f"Node: {anime.display_title} · "
                    f"Status: {anime.personal_status_label} · "
                    f"Created locally: {created}"
                ),
            )

            return redirect(next_url)

        updated_list_status = client.update_anime_my_list_status(
            anime_id=mal_id,
            status="plan_to_watch",
            num_watched_episodes=0,
            score=0,
            is_rewatching=False,
        )

        anime_details = client.fetch_anime_details(mal_id)

        anime_payload = {
            "node": anime_details,
            "list_status": {
                "status": updated_list_status.get("status", "plan_to_watch"),
                "score": updated_list_status.get("score", 0),
                "num_episodes_watched": updated_list_status.get(
                    "num_episodes_watched",
                    0,
                ),
                "is_rewatching": updated_list_status.get(
                    "is_rewatching",
                    False,
                ),
                "updated_at": updated_list_status.get("updated_at"),
            },
        }

        anime, created = upsert_anime_entry(anime_payload)

        try:
            sync_airing_data_for_dashboard()
        except Exception as airing_error:
            messages.warning(
                request,
                (
                    "Anime added to Plan to Watch, but Episode Signals sync failed. "
                    f"Reason: {airing_error}"
                ),
            )
            return redirect(next_url)

        messages.success(
            request,
            (
                "Anime added to MyAnimeList Plan to Watch and synchronized locally. "
                f"Node: {anime.display_title} · "
                f"Created locally: {created}"
            ),
        )

    except Exception as error:
        messages.error(
            request,
            (
                "Add to Plan failed. "
                "No local status was changed unless MyAnimeList accepted the update. "
                f"Reason: {error}"
            ),
        )

    return redirect(next_url)
    
