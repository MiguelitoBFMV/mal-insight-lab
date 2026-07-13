from datetime import timedelta

from django.shortcuts import render
from django.utils import timezone

from .models import AnimeEntry


def dashboard(request):
    now = timezone.now()
    three_months_ago = now - timedelta(days=90)

    anime_entries = AnimeEntry.objects.all()

    total_anime = anime_entries.count()

    watching_entries = anime_entries.filter(list_status="watching")
    completed_rewatch_entries = anime_entries.filter(
        list_status="completed",
        is_rewatching=True,
    )

    currently_airing_count = anime_entries.filter(
        airing_status="currently_airing"
    ).count()

    finished_airing_count = anime_entries.filter(
        airing_status="finished_airing"
    ).count()

    old_watching_entries = watching_entries.filter(
        updated_at_mal__lt=three_months_ago
    ).order_by("updated_at_mal")

    recent_watching_entries = watching_entries.filter(
        updated_at_mal__gte=three_months_ago
    ).order_by("-updated_at_mal")

    almost_finished_entries = watching_entries.filter(
        num_episodes__gt=0,
        num_episodes_watched__gt=0,
    )

    almost_finished_entries = [
        anime
        for anime in almost_finished_entries
        if anime.num_episodes > 0
        and anime.num_episodes_watched / anime.num_episodes >= 0.7
    ]

    context = {
        "total_anime": total_anime,
        "watching_count": watching_entries.count(),
        "rewatching_count": completed_rewatch_entries.count(),
        "currently_airing_count": currently_airing_count,
        "finished_airing_count": finished_airing_count,
        "old_watching_entries": old_watching_entries,
        "recent_watching_entries": recent_watching_entries,
        "almost_finished_entries": almost_finished_entries,
    }

    return render(request, "mal_data/dashboard.html", context)