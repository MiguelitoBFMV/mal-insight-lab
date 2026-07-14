from datetime import timedelta

from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from .models import AnimeEntry


def dashboard(request):
    now = timezone.now()
    three_months_ago = now - timedelta(days=90)

    anime_entries = AnimeEntry.objects.all()

    total_anime = anime_entries.count()

    watching_entries = anime_entries.filter(list_status="watching")
    on_hold_entries = anime_entries.filter(list_status="on_hold")
    plan_to_watch_entries = anime_entries.filter(list_status="plan_to_watch")
    completed_entries = anime_entries.filter(list_status="completed")
    dropped_entries = anime_entries.filter(list_status="dropped")
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
        "on_hold_count": on_hold_entries.count(),
        "plan_to_watch_count": plan_to_watch_entries.count(),
        "on_hold_entries": on_hold_entries.order_by("-score", "-updated_at_mal")[:10],
        "plan_to_watch_entries": plan_to_watch_entries.order_by("-updated_at_mal")[:10],
        "completed_count": completed_entries.count(),
        "dropped_count": dropped_entries.count(),
    }

    return render(request, "mal_data/dashboard.html", context)


def anime_status_list(request, status):
    valid_statuses = {
        "watching": "Watching",
        "on_hold": "On hold",
        "plan_to_watch": "Plan to watch",
        "completed": "Completed",
        "dropped": "Dropped",
    }

    if status not in valid_statuses:
        raise Http404("Estado de anime no válido")

    anime_entries = AnimeEntry.objects.filter(list_status=status)

    airing_filter = request.GET.get("airing")

    valid_airing_statuses = {
        "finished_airing": "Finalizados",
        "currently_airing": "En emisión",
        "not_yet_aired": "Por emitir",
    }

    if airing_filter in valid_airing_statuses:
        anime_entries = anime_entries.filter(airing_status=airing_filter)
    else:
        airing_filter = None

    # Orden inicial según el tipo de lista
        sort = request.GET.get("sort")

    sort = request.GET.get("sort")

    allowed_sorts = {
        "title": "title",
        "-title": "-title",
        "score": "score",
        "-score": "-score",
        "num_episodes": "num_episodes",
        "-num_episodes": "-num_episodes",
        "num_episodes_watched": "num_episodes_watched",
        "-num_episodes_watched": "-num_episodes_watched",
        "airing_status": "airing_status",
        "-airing_status": "-airing_status",
        "updated_at_mal": "updated_at_mal",
        "-updated_at_mal": "-updated_at_mal",
    }

    if sort in allowed_sorts:
        anime_entries = anime_entries.order_by(allowed_sorts[sort])
    else:
        if status == "plan_to_watch":
            sort = "title"
            anime_entries = anime_entries.order_by("title")
        elif status in {"completed", "dropped"}:
            sort = "-updated_at_mal"
            anime_entries = anime_entries.order_by("-updated_at_mal")
        elif status == "on_hold":
            sort = "title"
            anime_entries = anime_entries.order_by("title")
        else:
            sort = "-updated_at_mal"
            anime_entries = anime_entries.order_by("-updated_at_mal")

    paginator = Paginator(anime_entries, 50)

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "status": status,
        "status_label": valid_statuses[status],
        "page_obj": page_obj,
        "anime_entries": page_obj.object_list,
        "total_entries": paginator.count,
        "airing_filter": airing_filter,
        "valid_airing_statuses": valid_airing_statuses,
        "sort": sort,
        "media_type": "media_type",
        "-media_type": "-media_type",
    }

    return render(request, "mal_data/anime_status_list.html", context)