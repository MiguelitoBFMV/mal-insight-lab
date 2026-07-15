from datetime import timedelta

from django.core.paginator import Paginator
from django.http import Http404
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import AnimeEntry, AnimeRelation, AnimeSyncEvent
from mal_data.services.anime_relations_sync import sync_anime_relations
from mal_data.services.anime_list_sync import sync_all_anime_statuses

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

    for relation in sequel_relations:
        if relation.target_mal_id in seen_target_ids:
            continue

        target_anime = AnimeEntry.objects.filter(mal_id=relation.target_mal_id).first()

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

        messages.success(
            request,
            (
                "Lista de anime sincronizada desde MAL. "
                f"Total MAL: {total_entries} · "
                f"Creados: {created_entries} · "
                f"Actualizados: {updated_entries}"
            ),
        )
    except Exception as error:
        messages.error(
            request,
            f"No se pudo sincronizar la lista de anime: {error}",
        )

    return redirect("dashboard")