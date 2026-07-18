from datetime import timedelta

from django.core.paginator import Paginator
from django.http import Http404
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.db.models import Case, IntegerField, Q, Value, When

from mal_data.models import (
    AnimeAiringData,
    AnimeEntry,
    AnimeMetadata,
    AnimeRelation,
    AnimeSyncEvent,
    ManualTrackedAnime,
    SeasonalAnime
)
from mal_data.services.anime_relations_sync import sync_anime_relations
from mal_data.services.anime_list_sync import sync_all_anime_statuses
from mal_data.services.anilist_airing_sync import sync_airing_data_for_dashboard
from mal_data.services.anilist_client import AniListClient
from mal_data.services.manual_tracked_sync import sync_manual_tracked_anime_entries, sync_manual_tracked_anime_entry
from mal_data.services.anime_metadata_sync import sync_anime_metadata

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
    rewatching_entries = anime_entries.filter(is_rewatching=True)

    broadcast_watchlist_entries = (
        plan_to_watch_entries.filter(airing_status="currently_airing").order_by("-updated_at_mal", "title")[:10]
    )

    episode_signal_data = (
        AnimeAiringData.objects
        .select_related("anime")
        .filter(
            Q(anime__list_status="watching")
            | Q(anime__is_rewatching=True)
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
        is_rewatching = anime.is_rewatching
        is_longrun = (
            airing_data.episodes_aired_estimated >= 60
            or (anime.num_episodes and anime.num_episodes >= 60)
        )

        if is_rewatching:
            group = 3
        elif is_finished:
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
        "rewatching_count": rewatching_entries.count(),
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
        "all": "All anime",
        "watching": "Watching",
        "completed": "Completed",
        "plan_to_watch": "Plan to watch",
        "on_hold": "On hold",
        "dropped": "Dropped",
    }

    if status not in valid_statuses:
        raise Http404("Estado de anime no válido")

    status_order = [
        "watching",
        "completed",
        "plan_to_watch",
        "on_hold",
        "dropped",
    ]

    status_filter_options = [
        (status_key, valid_statuses[status_key])
        for status_key in status_order
    ]

    if status == "all":
        selected_statuses = request.GET.getlist("statuses")

        selected_statuses_query = ""

        if status == "all":
            selected_statuses_query = "".join(
                f"&statuses={selected_status}"
                for selected_status in selected_statuses
            )

        if not selected_statuses:
            selected_statuses = status_order.copy()

        selected_statuses = [
            selected_status
            for selected_status in selected_statuses
            if selected_status in status_order
        ]

        if len(selected_statuses) == 1:
            return redirect("anime_status_list", status=selected_statuses[0])

        if not selected_statuses:
            selected_statuses = status_order.copy()

        anime_entries = AnimeEntry.objects.filter(
            list_status__in=selected_statuses
        )
    else:
        selected_statuses = [status]
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
        if status == "all":
            sort = "status_priority"

            status_priority = Case(
                When(list_status="watching", then=Value(0)),
                When(list_status="completed", then=Value(1)),
                When(list_status="plan_to_watch", then=Value(2)),
                When(list_status="on_hold", then=Value(3)),
                When(list_status="dropped", then=Value(4)),
                default=Value(99),
                output_field=IntegerField(),
            )

            anime_entries = anime_entries.annotate(
                status_priority=status_priority
            ).order_by(
                "status_priority",
                "-updated_at_mal",
                "title",
            )

        elif status == "plan_to_watch":
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
        "status_order": status_order,
        "selected_statuses": selected_statuses,
        "status_filter_options": status_filter_options,
        "selected_statuses_query": selected_statuses_query,
    }

    return render(request, "mal_data/anime_status_list.html", context)

def anime_relations_detail(request, mal_id):
    anime = AnimeEntry.objects.filter(mal_id=mal_id).first()
    anime_metadata = None

    if anime is None:
        anime_metadata = AnimeMetadata.objects.filter(mal_id=mal_id).first()

        if anime_metadata is None:
            try:
                anime_metadata, _ = sync_anime_metadata(mal_id)
            except Exception:
                anime_metadata = None

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

    def relation_sort_key(relation):
        relation_type_priority = {
            "sequel": 0,
            "prequel": 1,
            "parent_story": 2,
            "side_story": 3,
            "spin_off": 4,
            "alternative_version": 5,
            "alternative_setting": 6,
            "summary": 7,
            "full_story": 8,
            "other": 9,
            "character": 10,
        }

        media_type_priority = {
            "movie": 0,
            "ova": 1,
            "special": 2,
            "tv_special": 3,
            "ona": 4,
            "tv": 5,
            "music": 8,
            "pv": 9,
            "cm": 10,
        }

        status_priority = {
            "watching": 0,
            "completed": 1,
            "plan_to_watch": 2,
            "on_hold": 3,
            "dropped": 4,
        }

        local_status = relation.target_local_list_status

        local_group = 0 if local_status else 1
        local_status_order = status_priority.get(local_status, 99)

        media_type = relation.target_display_media_type
        media_type_order = media_type_priority.get(
            str(media_type).lower() if media_type else "",
            99,
        )

        try:
            score = int(relation.target_display_score)
        except (TypeError, ValueError):
            score = 0

        return (
            0 if relation.relation_source_type == "anime" else 1,
            local_group,
            local_status_order,
            relation_type_priority.get(relation.relation_type, 99),
            media_type_order,
            -score,
            relation.target_display_title.lower(),
        )


    relations = list(
        AnimeRelation.objects.filter(source_mal_id=mal_id)
    )

    relations = sorted(relations, key=relation_sort_key)

    anime_relations = [
        relation
        for relation in relations
        if relation.relation_source_type == "anime"
    ]

    manga_relations = [
        relation
        for relation in relations
        if relation.relation_source_type == "manga"
    ]

    low_priority_relation_types = {
        "summary",
        "character",
        "other",
    }

    low_priority_media_types = {
        "music",
        "pv",
        "cm",
    }

    priority_relation_types = {
        "sequel",
        "prequel",
        "parent_story",
        "full_story",
        "side_story",
        "spin_off",
        "alternative_version",
        "alternative_setting",
    }

    local_priority_nodes = []
    local_completed_nodes = []
    external_priority_nodes = []
    external_low_priority_nodes = []
    unknown_nodes = []

    for relation in anime_relations:
        media_type = (relation.target_display_media_type or "").lower()
        relation_type = relation.relation_type or ""

        is_low_priority = (
            relation_type in low_priority_relation_types
            or media_type in low_priority_media_types
        )

        if relation.has_local_target:
            target_entry = relation.target_anime_entry
            local_status = target_entry.list_status if target_entry else relation.target_local_list_status

            if local_status == "completed":
                local_completed_nodes.append(relation)
            elif local_status != "dropped":
                local_priority_nodes.append(relation)
            else:
                external_low_priority_nodes.append(relation)

        elif relation.is_external_metadata_node:
            if is_low_priority:
                external_low_priority_nodes.append(relation)
            elif relation_type in priority_relation_types:
                external_priority_nodes.append(relation)
            else:
                external_low_priority_nodes.append(relation)

        else:
            unknown_nodes.append(relation)

    franchise_audit = {
        "local_priority_nodes": local_priority_nodes,
        "local_completed_nodes": local_completed_nodes,
        "external_priority_nodes": external_priority_nodes,
        "external_low_priority_nodes": external_low_priority_nodes,
        "unknown_nodes": unknown_nodes,
        "local_priority_count": len(local_priority_nodes),
        "local_completed_count": len(local_completed_nodes),
        "external_priority_count": len(external_priority_nodes),
        "external_low_priority_count": len(external_low_priority_nodes),
        "unknown_count": len(unknown_nodes),
    }

    if anime:
        source_title = anime.display_title
        source_picture_url = anime.main_picture_url
        source_status = anime.personal_status_label
        source_progress = f"{anime.num_episodes_watched} / {anime.num_episodes or 'TBD'}"
    elif anime_metadata:
        source_title = anime_metadata.display_title
        source_picture_url = anime_metadata.main_picture_url
        source_status = "Not local"
        source_progress = f"- / {anime_metadata.num_episodes or 'TBD'}"
    else:
        source_title = "Unknown Source Node"
        source_picture_url = ""
        source_status = "Unknown"
        source_progress = "-"
    
    context = {
        "anime": anime,
        "mal_id": mal_id,
        "anime_relations": anime_relations,
        "manga_relations": manga_relations,
        "total_relations": len(relations),
        "sync_result": sync_result,
        "sync_error": sync_error,
        "source_title": source_title,
        "source_picture_url": source_picture_url,
        "source_status": source_status,
        "source_progress": source_progress,
        "franchise_audit": franchise_audit,
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

def rescue_anime_from_search_view(request):
    if request.method != "POST":
        return redirect("anime_search")

    mal_id = request.POST.get("mal_id")
    title_snapshot = request.POST.get("title_snapshot", "").strip()
    status = request.POST.get("status", "watching")
    episodes_watched = request.POST.get("episodes_watched") or 0
    score = request.POST.get("score") or 0

    if not mal_id:
        messages.error(request, "Cannot rescue anime without MAL ID.")
        return redirect("anime_search")

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

        return redirect("anime_relations_detail", mal_id=anime.mal_id)

    except Exception as error:
        messages.error(request, f"Rescue failed: {error}")

    return redirect("anime_search")

def seasonal_board(request):
    season = request.GET.get("season", "SUMMER").upper()
    year = int(request.GET.get("year", 2026))
    format_filter = request.GET.get("format", "all")
    local_filter = request.GET.get("local", "all")

    seasonal_anime = SeasonalAnime.objects.filter(
        season=season,
        season_year=year,
    )

    if format_filter != "all":
        seasonal_anime = seasonal_anime.filter(format=format_filter.upper())

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

    context = {
        "season": season,
        "year": year,
        "format_filter": format_filter,
        "local_filter": local_filter,
        "season_options": ["WINTER", "SPRING", "SUMMER", "FALL"],
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
        "items": enriched_items,
        "total_items": len(enriched_items),
    }

    return render(request, "mal_data/seasonal_board.html", context)

def add_seasonal_to_plan_view(request):
    if request.method != "POST":
        return redirect("seasonal_board")

    mal_id = request.POST.get("mal_id")
    title_snapshot = request.POST.get("title_snapshot", "").strip()
    next_url = request.POST.get("next") or "seasonal_board"

    if not mal_id:
        messages.error(request, "Cannot add seasonal anime without MAL ID.")
        return redirect(next_url)

    try:
        tracked_entry, _ = ManualTrackedAnime.objects.update_or_create(
            mal_id=int(mal_id),
            defaults={
                "title_snapshot": title_snapshot,
                "status": "plan_to_watch",
                "episodes_watched": 0,
                "score": 0,
                "is_rewatching": False,
                "active": True,
            },
        )

        anime, created = sync_manual_tracked_anime_entry(tracked_entry)

        messages.success(
            request,
            (
                "Seasonal anime added to Plan to Watch. "
                f"Node: {anime.display_title} · "
                f"Created: {created}"
            ),
        )

        return redirect(next_url)

    except Exception as error:
        messages.error(request, f"Seasonal add failed: {error}")
        return redirect(next_url)
    
