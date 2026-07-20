from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from mal_data.models import AnimeEntry, ManualTrackedAnime
from mal_data.services.anilist_client import AniListClient
from mal_data.services.manual_tracked_sync import (
    sync_manual_tracked_anime_entry,
)

def anime_search_view(request):
    query = request.GET.get("q", "").strip()
    results = []
    search_error = None

    if query:
        try:
            client = AniListClient()
            candidates = client.search_anime_candidates(query)

            for candidate in candidates:
                mal_id = candidate.get("idMal")
                local_entry = None
                manual_entry = None

                if mal_id:
                    local_entry = AnimeEntry.objects.filter(mal_id=mal_id).first()
                    manual_entry = ManualTrackedAnime.objects.filter(mal_id=mal_id).first()

                results.append(
                    {
                        "anilist_id": candidate.get("id"),
                        "mal_id": mal_id,
                        "title": candidate.get("title") or {},
                        "status": candidate.get("status"),
                        "episodes": candidate.get("episodes"),
                        "cover_url": (
                            (candidate.get("coverImage") or {}).get("large")
                            or (candidate.get("coverImage") or {}).get("medium")
                        ),
                        "next_airing_episode": (
                            (candidate.get("nextAiringEpisode") or {}).get("episode")
                        ),
                        "local_entry": local_entry,
                        "manual_entry": manual_entry,
                    }
                )
        except Exception as error:
            search_error = str(error)

    def search_result_priority(result):
        local_entry = result["local_entry"]
        manual_entry = result["manual_entry"]
        status = result["status"]

        if local_entry:
            local_group = 0
        elif manual_entry:
            local_group = 1
        else:
            local_group = 2

        has_mal_id_group = 0 if result["mal_id"] else 1
        airing_group = 0 if status == "RELEASING" else 1

        return (
            local_group,
            has_mal_id_group,
            airing_group,
            result["title"].get("romaji") or "",
        )


    results = sorted(results, key=search_result_priority)

    context = {
        "query": query,
        "results": results,
        "search_error": search_error,
    }

    return render(request, "mal_data/anime_search.html", context)

@login_required
@require_POST
def rescue_anime_from_search_view(request):

    mal_id = request.POST.get("mal_id")
    title_snapshot = request.POST.get("title_snapshot", "").strip()
    status = request.POST.get("status", "watching")
    episodes_watched = request.POST.get("episodes_watched") or 0
    score = request.POST.get("score") or 0

    if not mal_id:
        messages.error(request, "Cannot rescue anime without MAL ID.")
        return redirect("mal_insights:anime_search")

    try:
        tracked_entry, _ = ManualTrackedAnime.objects.update_or_create(
            mal_id=int(mal_id),
            defaults={
                "title_snapshot": title_snapshot,
                "status": status,
                "episodes_watched": int(episodes_watched),
                "score": int(score),
                "is_rewatching": False,
                "active": True,
            },
        )

        anime, created = sync_manual_tracked_anime_entry(tracked_entry)

        messages.success(
            request,
            (
                "Anime rescued and tracked. "
                f"Node: {anime.display_title} · "
                f"Status: {anime.personal_status_label} · "
                f"Created: {created}"
            ),
        )

        return redirect("mal_insights:anime_relations_detail", mal_id=anime.mal_id)

    except Exception as error:
        messages.error(request, f"Rescue failed: {error}")

    return redirect("mal_insights:anime_search")