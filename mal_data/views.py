from datetime import timedelta

from django.core.paginator import Paginator
from django.http import Http404
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import AnimeAiringData, AnimeEntry, AnimeRelation, AnimeSyncEvent
from mal_data.services.anime_relations_sync import sync_anime_relations
from mal_data.services.anime_list_sync import sync_all_anime_statuses
from mal_data.services.anilist_airing_sync import sync_airing_data_for_dashboard
from mal_data.services.manual_tracked_sync import sync_manual_tracked_anime_entries

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

    broadcast_watchlist_entries = (
        plan_to_watch_entries.filter(airing_status="currently_airing").order_by("-updated_at_mal", "title")[:10]
    )

    episode_signal_data = (
        AnimeAiringData.objects
        .select_related("anime")
        .filter(
            anime__list_status="watching",
        )
    )

    episode_signal_entries = [
        airing_data
        for airing_data in episode_signal_data
        if airing_data.pending_episodes_for_user > 0
    ]


    def episode_signal_priority(airing_data):
        anime = airing_data.anime

        is_finished = anime.airing_status == "finished_airing"

        is_longrun = (
            airing_data.episodes_aired_estimated >= 60
            or (anime.num_episodes and anime.num_episodes >= 60)
        )

        if is_finished:
            group = 2
        elif is_longrun:
            group = 1
        else:
            group = 0

        next_airing_sort = (
            airing_data.next_airing_at.timestamp()
            if airing_data.next_airing_at
            else 0
        )

        return (
            group,
            -next_airing_sort,
            -airing_data.pending_episodes_for_user,
            anime.title,
        )


    episode_signal_entries = sorted(
        episode_signal_entries,
        key=episode_signal_priority,
    )[:15]

    fallback_active_entries = watching_entries.order_by("-updated_at_mal")[:4]

    priority_source_entries = list(watching_entries) + list(completed_entries)

    source_mal_ids = [anime.mal_id for anime in priority_source_entries]

    sequel_relations = (
        AnimeRelation.objects
        .filter(
            source_mal_id__in=source_mal_ids,
            relation_source_type="anime",
            relation_type="sequel",
        )
        .order_by("source_title", "target_title")
    )

    sequel_recommendations = []
    seen_target_ids = set()

    broadcast_watchlist_ids = set(
        broadcast_watchlist_entries.values_list("mal_id", flat=True)
    )

    for relation in sequel_relations:
        if relation.target_mal_id in seen_target_ids:
            continue

        target_anime = AnimeEntry.objects.filter(mal_id=relation.target_mal_id).first()

        if target_anime and target_anime.mal_id in broadcast_watchlist_ids:
            continue

        if target_anime and target_anime.list_status in ["completed", "watching"]:
            continue

        source_anime = AnimeEntry.objects.filter(mal_id=relation.source_mal_id).first()

        recommendation = {
            "source_title": source_anime.display_title if source_anime else relation.source_title,
            "target_title": target_anime.display_title if target_anime else relation.target_title,
            "target_mal_id": relation.target_mal_id,
            "target_status": target_anime.personal_status_label if target_anime else "Not in local list",
            "target_airing_status": (
                target_anime.airing_status
                if target_anime
                else relation.target_status or "unknown"
            ),
        }

        sequel_recommendations.append(recommendation)
        seen_target_ids.add(relation.target_mal_id)

    sequel_recommendations = sequel_recommendations[:10]

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

    backlog_total = completed_entries.count() + plan_to_watch_entries.count()

    if backlog_total > 0:
        backlog_clear_ratio = round(completed_entries.count() / backlog_total * 100)
    else:
        backlog_clear_ratio = 0

    spotlight_anime = (
        watching_entries
        .exclude(title_japanese__isnull=True)
        .exclude(title_japanese="")
        .order_by("-score", "-updated_at_mal")
        .first()
    )

    latest_sync_events = (AnimeSyncEvent.objects.select_related("anime").order_by("-created_at")[:15])

    last_synced_entry = anime_entries.order_by("-last_synced_at").first()

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
        "backlog_clear_ratio": backlog_clear_ratio,
        "backlog_total": backlog_total,
        "spotlight_anime": spotlight_anime,
        "latest_sync_events": latest_sync_events,
        "last_synced_entry": last_synced_entry,
        "sequel_recommendations": sequel_recommendations,
        "broadcast_watchlist_entries": broadcast_watchlist_entries,
        "episode_signal_entries": episode_signal_entries,
        "fallback_active_entries": fallback_active_entries,
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
        "media_type": "media_type",
        "-media_type": "-media_type",
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
    }

    return render(request, "mal_data/anime_status_list.html", context)

def anime_relations_detail(request, mal_id):
    anime = AnimeEntry.objects.filter(mal_id=mal_id).first()

    existing_relations = AnimeRelation.objects.filter(
        source_mal_id=mal_id
    ).exists()

    sync_result = None
    sync_error = None

    if not existing_relations:
        try:
            sync_result = sync_anime_relations(mal_id)
        except Exception as error:
            sync_error = str(error)

    relations = AnimeRelation.objects.filter(
        source_mal_id=mal_id
    ).order_by(
        "relation_source_type",
        "relation_type",
        "target_title",
    )

    anime_relations = relations.filter(relation_source_type="anime")
    manga_relations = relations.filter(relation_source_type="manga")

    context = {
        "anime": anime,
        "mal_id": mal_id,
        "anime_relations": anime_relations,
        "manga_relations": manga_relations,
        "total_relations": relations.count(),
        "sync_result": sync_result,
        "sync_error": sync_error,
    }

    return render(request, "mal_data/anime_relations_detail.html", context)

def sync_anime_relations_view(request, mal_id):
    if request.method != "POST":
        return redirect("anime_relations_detail", mal_id=mal_id)

    try:
        result = sync_anime_relations(mal_id)

        messages.success(
            request,
            (
                "Relaciones actualizadas desde MAL. "
                f"Anime relacionados: {result['related_anime_count']} · "
                f"Manga relacionados: {result['related_manga_count']}"
            ),
        )
    except Exception as error:
        messages.error(
            request,
            f"No se pudieron actualizar las relaciones: {error}",
        )

    return redirect("anime_relations_detail", mal_id=mal_id)


def sync_anime_list_view(request):
    if request.method != "POST":
        return redirect("dashboard")

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

    return redirect("dashboard")