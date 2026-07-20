from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from mal_data.services.anime_list_sync import sync_all_anime_statuses
from mal_data.services.anilist_airing_sync import (
    sync_airing_data_for_dashboard,
)
from mal_data.services.manual_tracked_sync import (
    sync_manual_tracked_anime_entries,
)

@login_required
@require_POST
def sync_anime_list_view(request):

    try:
        results = sync_all_anime_statuses()

        total_entries = sum(result["total"] for result in results)
        created_entries = sum(result["created"] for result in results)
        updated_entries = sum(result["updated"] for result in results)

        manual_results = sync_manual_tracked_anime_entries()
        manual_ok_count = sum(1 for result in manual_results if result["ok"])
        manual_error_count = sum(1 for result in manual_results if not result["ok"])

        airing_results = sync_airing_data_for_dashboard()
        airing_ok_count = sum(1 for result in airing_results if result["ok"])
        airing_error_count = sum(1 for result in airing_results if not result["ok"])

        messages.success(
            request,
            (
                "Anime data synchronized from MAL, manual tracked entries and AniList. "
                f"MAL total: {total_entries} · "
                f"Created: {created_entries} · "
                f"Updated: {updated_entries} · "
                f"Manual tracked OK: {manual_ok_count} · "
                f"Manual tracked errors: {manual_error_count} · "
                f"Airing OK: {airing_ok_count} · "
                f"Airing errors: {airing_error_count}"
            ),
        )
    except Exception as error:
        messages.error(
            request,
            f"Anime sync failed: {error}",
        )

    return redirect("mal_insights:dashboard")

